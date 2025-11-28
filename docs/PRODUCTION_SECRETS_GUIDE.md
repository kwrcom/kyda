# Управление Production-секретами в Vault

В отличие от Dev-режима, где мы используем скрипт `vault-init` с захардкоженными значениями, в Production секреты загружаются вручную администратором, а приложения используют безопасный метод аутентификации (AppRole).

## 1. Как загрузить секреты (Operator Workflow)

В проде вы подключаетесь к Vault как администратор и загружаете секреты вручную.

### Способ А: Через CLI (Рекомендуемый)

1.  **Подключитесь к Vault:**
    ```bash
    export VAULT_ADDR='https://vault.your-domain.com:8200'
    vault login
    # Введите ваш токен администратора
    ```

2.  **Запишите секреты:**
    *Совет: Поставьте пробел перед командой, чтобы она не сохранилась в истории терминала.*

    **Backend:**
    ```bash
     vault kv put secret/backend \
      postgres_user=prod_user \
      postgres_password=VERY_COMPLEX_PASSWORD_X99 \
      postgres_db=mlflow_prod \
      minio_access_key=AKIAIOSFODNN7EXAMPLE \
      minio_secret_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
      jwt_algorithm=RS256
    ```

    **Airflow:**
    ```bash
     vault kv put secret/airflow \
      postgres_user=airflow_prod \
      postgres_password=ANOTHER_COMPLEX_PASSWORD \
      postgres_db=airflow_prod \
      fernet_key=YOUR_GENERATED_FERNET_KEY \
      webserver_secret_key=YOUR_WEBSERVER_KEY \
      minio_access_key=AKIAIOSFODNN7EXAMPLE \
      minio_secret_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    ```

### Способ Б: Через JSON файл

Если секретов много, удобнее использовать файл.

1.  Создайте `secrets.json` (локально):
    ```json
    {
      "postgres_user": "prod_user",
      "postgres_password": "SUPER_SECRET_PASSWORD",
      "postgres_db": "mlflow_prod",
      "minio_access_key": "prod_key",
      "minio_secret_key": "prod_secret",
      "jwt_algorithm": "RS256"
    }
    ```

2.  Загрузите в Vault:
    ```bash
    vault kv put secret/backend @secrets.json
    ```

3.  **Сразу удалите файл:**
    ```bash
    rm secrets.json
    ```

## 2. Как настроить приложение (AppRole)

В проде нельзя использовать `root` токен. Мы используем **AppRole**.

### Шаг 1: Настройка AppRole (Администратор)

Выполните эти команды один раз при настройке кластера:

```bash
# Включить AppRole
vault auth enable approle

# Создать роль для backend
vault write auth/approle/role/backend \
    token_policies="backend-policy" \
    token_ttl=1h \
    token_max_ttl=4h

# Создать роль для airflow
vault write auth/approle/role/airflow \
    token_policies="airflow-policy" \
    token_ttl=1h \
    token_max_ttl=4h
```

### Шаг 2: Получение ID (Администратор / CI/CD)

1.  **RoleID** (Идентификатор роли, не секретен):
    ```bash
    vault read auth/approle/role/backend/role-id
    # Пример: db02de05-fa39-4855-059b-67221c5c2f63
    ```

2.  **SecretID** (Пароль роли, секретен, выдается при деплое):
    ```bash
    vault write -f auth/approle/role/backend/secret-id
    # Пример: 6a174c20-f6de-a53c-74d2-6018fcceff64
    ```

### Шаг 3: Настройка переменных окружения

В вашем `docker-compose.yml` или Kubernetes Deployment для продакшена:

```yaml
services:
  backend:
    environment:
      - VAULT_ADDR=https://vault.your-domain.com:8200
      # Вместо VAULT_TOKEN используем:
      - VAULT_ROLE_ID=db02de05-fa39-4855-059b-67221c5c2f63
      - VAULT_SECRET_ID=6a174c20-f6de-a53c-74d2-6018fcceff64
```

**Примечание:** Код приложения (`main.py` и `vault_helper.py`) уже обновлен и автоматически переключится на AppRole, если увидит эти переменные.

## 3. Ротация секретов

Чтобы сменить пароль базы данных без простоя:

1.  Создайте нового пользователя в БД.
2.  Обновите секрет в Vault:
    ```bash
    vault kv put secret/backend postgres_user=new_user postgres_password=new_pass ...
    ```
3.  Перезапустите backend сервис (он подтянет новые креды при старте).
4.  Удалите старого пользователя в БД.
