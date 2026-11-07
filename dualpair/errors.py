class DualPairError(Exception):
    """An error with a stable code, so the GUI can show a translated message.

    The text of each code lives in i18n.py ("err.<code>").
    """

    def __init__(self, code: str, **params):
        self.code = code
        self.params = params
        super().__init__(code)

    def to_dict(self):
        from .i18n import t
        return {"code": self.code, "params": self.params, "message": t("err." + self.code, **self.params)}

    def __str__(self):
        from .i18n import t
        return t("err." + self.code, **self.params)
