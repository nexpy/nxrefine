def __bootstrap__():
    global __bootstrap__, __loader__, __file__
    import pkg_resources
    import imp
    __file__ = pkg_resources.resource_filename(__name__, 'closest.so')
    __loader__ = None
    del __bootstrap__, __loader__
    imp.load_dynamic(__name__, __file__)


__bootstrap__()
