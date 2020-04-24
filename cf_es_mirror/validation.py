from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentfulType


def validate_request(headers, authorization, json_data):
    """
    :returns: Either an integer indicating the error type, or a tuple of the object and the action name.
              Possible return codes:
                 0: Invalid action/type
                -1: Invalid request
                -2: Invalid authentication
                -3: Invalid data
    """
    # As per https://www.contentful.com/developers/docs/references/content-management-api/#/reference/webhooks
    # The "X-Contentful-Topic" header is always sent. So if it is not sent, we are not dealing with
    #  a contentful webhook push
    if 'X-Contentful-Topic' not in headers:
        config.logger.info("Received request missing X-Contentful-Topic header")
        return -1

    # As per https://www.contentful.com/developers/docs/references/content-management-api/#/reference/webhooks
    # The "X-Contentful-Webhook-Name" header is always sent. So if it is not sent, we are not dealing with
    #  a contentful webhook push
    if 'X-Contentful-Webhook-Name' not in headers:
        config.logger.info("Received request missing X-Contentful-Webhook-Name header")
        return -1
    
    # As per https://www.contentful.com/developers/docs/references/content-management-api/#/reference/webhooks
    # Contentful uses the content-type 'application/vnd.contentful.management.v1+json by default, so if we
    #  do not receive this, we are not dealing with a contentful webhook push.
    content_type = headers.get("Content-Type")
    if not content_type or 'application/vnd.contentful.management.v1+json' not in content_type:
        config.logger.info(f"Received request with invalid Content-Type: '{content_type}'")
        return -1

    try:
        _, _type, action = headers['X-Contentful-Topic'].split('.', 2)
    except:
        return -1

    if config.WEBHOOK_AUTH:
        if authorization is None:
            auth_header = headers.get("Authorization", " ")
            auth_type, auth_info = auth_header.split(None, 1)
            if auth_type == "Basic":
                try:
                    username, password = base64.b64decode(auth_info).decode("ascii").split(":")
                except Exception:
                    return -2
                authorization = dict(username=username, password=password)
        try:
            if config.WEBHOOK_AUTH[authorization["username"]] != authorization["password"]:
                config.logger.info("Received unauthenticated request.")
                return -2
        except:
            config.logger.info("Received unauthenticated request.")
            return -2

    klass = ContentfulType.get_type(_type)
    if not klass:
        config.logger.info(f"Received webhook request for invalid type: '{_type}/{action}'")
        return -3

    if callable(json_data):  # Allow for lazy-loading the lazy data until we've validated the json content type.
        json_data = json_data()

    obj = klass(json_data)
    if not isinstance(obj, ContentfulType):
        return -3
    
    if not obj.valid_for_space():
        config.logger.info(f"Webhook request not valid for space: '{_type}/{action}'")
        return 0
    if action not in obj.ACTIONS:
        config.logger.info(f"Webhook requested invalid action: '{_type}/{action}'")
        return 0

    config.logger.debug(f"Webhook request validated: '{_type}/{action}'")    
    return obj, action
