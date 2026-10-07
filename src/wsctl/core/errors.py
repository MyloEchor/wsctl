class WsctlError(RuntimeError):
    """工作区管理操作失败。"""


class NotFoundError(WsctlError):
    """对象不存在。"""


class ValidationError(WsctlError):
    """输入或磁盘数据不符合约定。"""


class WriteDeniedError(WsctlError):
    """工作区没有开启 AI 写入权限。"""

