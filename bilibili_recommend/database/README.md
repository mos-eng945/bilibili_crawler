# Database Import

Import crawler output into MySQL.

## Setup

1. Create the tables.

如果 `mysql` 命令不在 PATH 中，使用完整路径：

```powershell
Get-Content schema.sql | & 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe' -u root -p
```

也可以先把 MySQL 的 `bin` 目录加入 PATH，然后直接运行：

```powershell
Get-Content schema.sql | mysql -u root -p
```

2. Edit `config.py` and set your MySQL password.

3. Install the Python driver:

```text
pip install -r requirements.txt
```

4. Import all data:

```text
python import_all.py
```

导入默认目录 `output`。如果需要导入其他目录，可以传入路径：

```powershell
python import_all.py "D:\另一个同学的目录\output"
```

也可以通过环境变量临时指定：

```powershell
$env:BILIBILI_OUTPUT_DIR = "D:\另一个同学的目录\output"
python import_all.py
```

The scripts are idempotent: rerunning them updates existing rows and skips
duplicate records.

