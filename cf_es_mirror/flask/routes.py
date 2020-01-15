from cf_es_mirror.flask.base import bp
from cf_es_mirror.validation import validate_request

from flask import request, abort, current_app

@bp.route('/webhook-update', methods=['POST'])
def webhook_update():
    validation = validate_request(request.headers, request.authorization, request.get_json)
    if validation == -1:
        abort(404)
    elif validation == -2:
        return '', 401
    elif validation == -3:
        return '', 204
    elif validation == 0:
        return '', 204
    elif not isinstance(validation, tuple):
        return '', 204

    obj, action = validation

    handler = getattr(obj, action)
    try:
        handler()
    except:
        return '', 500
    return '', 200
