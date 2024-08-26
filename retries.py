from tenacity import retry, stop_after_attempt, wait_random_exponential, RetryError, retry_if_not_exception_type

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def execution_with_backoff(cur, query, vars = None):
    cur.execute(query, vars)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def thread_creation_with_backoff(client):
    thread = client.beta.threads.create()
    return thread

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def thread_deletion_with_backoff(client, thread):
    client.beta.threads.delete(thread.id)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def message_creation_with_backoff(client, thread, content):
    client.beta.threads.messages.create(thread_id=thread.id, role="user", content=content)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def message_listing_with_backoff(client, thread):
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    return messages

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def message_deletion_with_backoff(client, message, thread):
    client.beta.threads.messages.delete(message_id=message.id, thread_id=thread.id)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def creation_and_polling_with_backoff(client, thread):
    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=os.environ["ASSISTANT_ID"])

    while run.status == "in_progress":
        pass

    if run.status == "failed":
        raise RetryError(run.last_error.message)
    elif run.status == "incomplete":
        raise RetryError(run.incomplete_details.reason)
    
    return run

def evaluate_question(question):
    if "question" not in question:
        raise Exception("attribute \"question\" not in JSON")
    elif type(question["question"]) is not str:
        raise Exception("value \"question\" is not string")
    elif "options" not in question:
        raise Exception("attribute \"options\" not in JSON")
    elif type(question["options"]) is not list:
        raise Exception("value \"options\" is not array")
    elif "answer" not in question:
        raise Exception("attribute \"answer\" not in JSON")
    elif type(question["answer"]) is not str:
        raise Exception("value \"answer\" is not string")
    elif len(question["options"]) > 3:
        raise Exception("value \"options\" has length greater than 3")
    elif question["answer"] not in question["options"]:
        raise Exception("value \"answer\" not in value \"options\"")
    
    for i, option in enumerate(question["options"]):
        if type(option) is not str:
            raise Exception(f"value \"options\"[{i}] is not string")

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), retry=retry_if_not_exception_type(RetryError))
def get_question_with_backoff(client, thread):
    run = creation_and_polling_with_backoff(client, thread)
    
    if run.status == "completed":
        try:
            messages = message_listing_with_backoff(client, thread)
        except RetryError as retry_error:
            message_deletion_with_backoff(client, messages.data[0], thread)
            retry_error.reraise()

        try:
            question = eval(messages.data[0].content[0].text.value)
            evaluate_question(question)
        except:
            message_deletion_with_backoff(client, messages.data[0], thread)
            raise
    else:
        raise RetryError(run.status)

    return question