CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'stdoutFormatter': {
            'format': '// %(levelname)s %(filename)s:%(lineno)d %(message)s'
        }
    },
    'handlers': {
        'streamHandler': {
            'class': 'logging.StreamHandler',
            'formatter': 'stdoutFormatter'
        },
    },
    'loggers': {
        'git2dot': {
            'handlers': ['streamHandler'],
            'level': 'ERROR',
            'propagate': True
        }
    }
}
