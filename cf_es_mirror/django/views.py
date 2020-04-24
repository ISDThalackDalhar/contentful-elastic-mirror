import json

from django.http import Http404

from cf_es_mirror.validation import validate_request

def webhook_update(request):
    body = None
    if request.body:
        try:
            body = json.loads(request.body)
        except:
            return HttpResponse(500)
    validation = validate_request(request.headers, None, body)
    if validation == -1:
        raise Http404("")
    elif validation == -2:
        return HttpResponse(status=401)
    elif validation == -3:
        return HttpResponse(status=204)
    elif validation == 0:
        return HttpResponse(status=204)
    elif not isinstance(validation, tuple):
        return HttpResponse(status=204)

    obj, action = validation

    handler = getattr(obj, action)
    try:
        handler()
    except:
        return HttpResponse(status=500)
    return HttpResponse(status=200)
