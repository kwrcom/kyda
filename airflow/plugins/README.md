# Airflow Plugins Directory

## Reason
This directory contains custom Airflow plugins, operators, sensors, and hooks.

## Usage
Create custom operators or hooks to extend Airflow functionality:

```
plugins/
├── operators/
│   └── custom_operator.py
├── sensors/
│   └── custom_sensor.py
└── hooks/
    └── custom_hook.py
```

## Example Custom Operator
```python
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

class MyCustomOperator(BaseOperator):
    @apply_defaults
    def __init__(self, my_param, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.my_param = my_param
    
    def execute(self, context):
        # Custom logic here
        self.log.info(f"Executing with param: {self.my_param}")
```
