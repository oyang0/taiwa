import os

from fbmessenger.elements import Text

def process_exception(exception):
    exception = f"{exception}"
    exception = exception.replace(os.environ["ASSISTANT_ID"], "?")
    exception = exception.replace(os.environ["DATABASE_URL"], "?")
    exception = exception.replace(os.environ["FB_PAGE_TOKEN"], "?")
    exception = exception.replace(os.environ["FB_VERIFY_TOKEN"], "?")
    exception = exception.replace(os.environ["OPENAI_API_KEY"], "?")
    exception = exception.replace(os.environ["SCHEMA"], "?")
    actions = [Text(text=exception).to_dict()]
    return actions