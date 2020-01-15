from blinker import signal

pre_index_remove = signal('pre-index-remove')
post_index_remove = signal('post-index-remove')

annotate_index_create = signal('annotate-index-create')
pre_index_create = signal('pre-index-create')
post_index_create = signal('post-index-create')

pre_entry_remove = signal('pre-entry-remove')
post_entry_remove = signal('post-entry-remove')

annotate_entry_index = signal('annotate-entry-index')
pre_entry_index = signal('pre-entry-index')
post_entry_index = signal('post-entry-index')


__all__ = [
    'pre_index_remove',
    'post_index_remove',

    'annotate_index_create',
    'pre_index_create',
    'post_index_create',

    'pre_entry_remove',
    'post_entry_remove',

    'annotate_entry_index',
    'pre_entry_index',
    'post_entry_index',
]
