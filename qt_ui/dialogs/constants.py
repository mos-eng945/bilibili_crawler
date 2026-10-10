"""数据浏览相关的共享常量。"""

# 预览文件最多读取的行数
PREVIEW_ROW_LIMIT = 5000
# 勾选「只显示关键列」时保留的列数
TABLE_COLUMN_LIMIT = 6
# 行数不超过该值时，长文本换行完整显示
WRAP_ROW_LIMIT = 200
# 这些后缀可在数据浏览里直接预览，不再交给系统默认程序
BROWSABLE_SUFFIXES = {".csv", ".json", ".srt"}
