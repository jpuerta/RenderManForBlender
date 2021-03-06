import logging
import logging.handlers
import os
from ..rman_utils import prefs_utils

LOGGING_DISABLED = 100
CRITICAL = logging.CRITICAL
ERROR    = logging.ERROR
WARNING  = logging.WARNING
INFO     = logging.INFO
VERBOSE  = 15
DEBUG    = logging.DEBUG
NOTSET   = logging.NOTSET

__LOG_LEVELS__ = { 'CRITICAL': logging.CRITICAL,
               'ERROR': logging.ERROR,
               'WARNING': WARNING,
               'INFO': logging.INFO,
               'VERBOSE': 15,
               'DEBUG': logging.DEBUG,
               'NOTSET':  logging.NOTSET}

__RFB_LOG_FILE__ = ''
__RFB_LOG_FILE_HANDLER__ = None

__RFB_CONSOLE_HANDLER__ = None
__RFB_LOG_LEVEL = None

# logger format
LOG_FMT = '[%(levelname)s] (%(threadName)-10s) %(name)s %(funcName)s: %(message)s'

def set_logger_level(level):
    """
    Set the logging level for this module. This is only useful if the module
    is not using another logger.
    """
    __log__.setLevel(level)

def logger_level():
    """Return the logger's current level"""
    return __log__.level

def set_logger(logger):
    """
    Make this module adopt another logger and coalesce outputs into one stream.
    """
    global __log__
    __log__ = logger

def init_log_level():
    global __LOG_LEVELS__
    global __RFB_LOG_LEVEL

    if 'RFB_LOG_LEVEL' in os.environ:
        __RFB_LOG_LEVEL = os.environ['RFB_LOG_LEVEL']
        set_logger_level(__LOG_LEVELS__[__RFB_LOG_LEVEL])

    __log__.debug('logger initialized')
    __log__.debug('   |_ logger: %d', logger_level())

def set_file_logger(logFile):
    global __RFB_LOG_FILE__
    global __RFB_LOG_FILE_HANDLER__
    global __log__

    err_msg = []
    if not os.path.exists(os.path.dirname(logFile)):
        # make sure the directories exist.
        try:
            os.makedirs(os.path.dirname(logFile))
        except (IOError, OSError) as err:
            err_msg.append('Could not create log directory in %s : %s' %
                        (logFile, err))
        if not os.access(logFile, os.W_OK | os.R_OK):
            err_msg.append('Log file is not writable %s' % (logFile))
            return

    if logFile:
        # generate up to 5 logs of 10MB each.
        __RFB_LOG_FILE_HANDLER__ = logging.handlers.RotatingFileHandler(logFile,
                                                    maxBytes=10485760,
                                                    backupCount=5)
        __RFB_LOG_FILE_HANDLER__.setLevel(DEBUG)
        # we use a different format for the disk log, to get a time stamp.
        fmtf = logging.Formatter('%(asctime)s %(levelname)8s {%(threadName)-10s}'
                                    ':  %(module)s %(funcName)s: %(message)s')
        __RFB_LOG_FILE_HANDLER__.setFormatter(fmtf)
        __log__.addHandler(__RFB_LOG_FILE_HANDLER__)    
        __RFB_LOG_FILE__ = logFile   

def check_log_level_preferences(): 
    global __RFB_LOG_LEVEL
    if __RFB_LOG_LEVEL:
        return

    rman_prefs = prefs_utils.get_addon_prefs()
    if rman_prefs and rman_prefs.rman_logging_level in __LOG_LEVELS__:
        level = __LOG_LEVELS__[rman_prefs.rman_logging_level]
        set_logger_level(level)
    else:
        set_logger_level(WARNING)       

def check_logfile_preferences():
    global __RFB_LOG_FILE__
    global __RFB_LOG_FILE_HANDLER__
    global __log__

    if __RFB_LOG_FILE__:
        return

    logFile = ''
    err_msg = []
    rman_prefs = prefs_utils.get_addon_prefs()
    if rman_prefs and rman_prefs.rman_logging_file:
        logFile = rman_prefs.rman_logging_file     

    if logFile:
        set_file_logger(logFile)

def rfb_log():
    """
    Return the logger.
    """

    # These are necessary because for some reason getting the preferences
    # in get_logger() seems to always fail
    if not __RFB_LOG_FILE__:
        check_logfile_preferences()
    if not __RFB_LOG_LEVEL:        
        check_log_level_preferences()

    return __log__


def get_logger(name):
    """
    Create a new configured logger and returns it.
    """
    log = logging.getLogger(name)
    # we don't set the logger's level to inherit from the parent logger.
    if log.handlers:
        return log
    fmt = logging.Formatter(LOG_FMT)
    shdlr = logging.StreamHandler()
    shdlr.setFormatter(fmt)
    log.addHandler(shdlr)

    if 'RFB_LOG_FILE' in os.environ:
        logFile = os.environ['RFB_LOG_FILE']    
        set_file_logger(logFile)

    log.propagate = False

    return log

__log__ = get_logger(__name__)
init_log_level()