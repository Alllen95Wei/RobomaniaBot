import psutil


def get_cpu_usage():
    return psutil.cpu_percent()


def get_ram_usage_detail():
    ram_usage = psutil.virtual_memory().percent
    ram_total = round(psutil.virtual_memory().total / (1024 ^ 3))
    ram_free = round(psutil.virtual_memory().free / (1024 ^ 3))
    ram_status = str(ram_usage) + "%" + "`(" + str(ram_free) + "MB / " + str(ram_total) + "MB)`"
    return ram_status
