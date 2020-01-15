DISABLED = dict(enabled=False)
NOT_INDEXED = dict(enabled=False)

# Default field types for ES
KEYWORD = dict(type="keyword")
TEXT = dict(type="text")
BOOL = dict(type="boolean")
DATE = dict(type="date")
INT = dict(type="integer")
LINK = {
    "properties": {
        "sys": {
            "properties": {
                "type": DISABLED,
                "linkType": KEYWORD,
                "id": KEYWORD
            }
        }
    }
}

# Contentful sys fields are generally all the same format
SYS = {
    "properties": {
        "id": {"type": "keyword"},
        "contentType": NOT_INDEXED,
        "type": KEYWORD,
        "space": LINK,
        "environment": NOT_INDEXED,
        "revision": INT,
        "createdAt": DATE,
        "updatedAt": DATE,
        "createdBy": NOT_INDEXED,  # TODO: Perhaps figure out how to best deal the *By fields ?
        "updatedBy": NOT_INDEXED,
        "publishedBy": NOT_INDEXED,
        "publishedAt": DATE,
        "firstPublishedAt": DATE,
        "publishedCounter": INT,
        "version": INT,
    }
}

# Fields to mapping types mapping
FIELDS = {
    "Symbol": TEXT,
    "Text": TEXT,
    "RichText": DISABLED,  # TODO: Figure out how to best index RichText
    "Object": DISABLED,
    "Boolean": BOOL,
    "Link": LINK,
    "Location": DISABLED,  # TODO: Figure out how to best index Location fields.
    "Integer": INT,
    "Date": DATE,
}

TYPES_MAPPING = {
    "properties": {
        "sys": SYS,
        "fields": DISABLED,
        "description": DISABLED,
        "displayField": DISABLED,
    }
}
