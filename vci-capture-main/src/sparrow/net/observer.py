from gibbs.interceptor import ConnectionGroupManager


class NotifyManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(NotifyManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """
        Initialize the ConnectionGroupManager instance.
        This method is called only once when the instance is created.
        """
        self.manager = ConnectionGroupManager()

    def __getattr__(self, name):
        """
        Forward all method calls to the ConnectionGroupManager instance.
        """
        return getattr(self.manager, name)
