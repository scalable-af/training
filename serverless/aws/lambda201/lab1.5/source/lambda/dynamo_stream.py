import boto3
import logging
import json
import os

# Setup our standard logger. We re-use the same format in most places so we have a standard presentation
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers[0].setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))

# We are going to emulate the few bits we need to fire off the building of our hugo site
# we will effectively fake the webhook. On the other side we check to see if this is 
# from the mocked stream handler, if it is we do fewer checks for validity.
def fake_webhook(event, context):
    # We take in an event, that is the dynamodb change event but since we are building
    # A static site that has to be compiled completely we aren't doing anything with it
    # we are just using it as a trigger for an event that rebuilds the whole site.
    # There are better less wasteful ways to do something like this but it works well for
    # demonstrating how a stream event can be used as a generic trigger

    # We need the full name of the repo, we can see this in the webhook that we logged in lab 1.3
    try:
        full_name = os.environ['full_name']
    except:
        raise Exception('Full Name not defined. Set the environment variable for the funcion')

    # We need the HTTPS clone_url, we can see this in the webhook that we logged in lab 1.3
    try:
        clone_url = os.environ['clone_url']
    except:
        raise Exception('Clone URL not defined. Set the environment variable for the funcion')

    # For modularity we don't bake in the name of the github processing webhook and instead specify it via env variable
    try:
        webhook_function = os.environ['webhook_function']
    except:
        raise Exception('Webhook Function not defined. Set the environment variable for the funcion')

    # Build our payload, using the same structure and the essential items from the real github webhook
    # Set a flag indicating that this payload is from another lambda function so that we can short circuit
    # some of our conditional login in the webhook and re-use the same function
    payload = {
        "repository": {
            "full_name": full_name,
            "clone_url": clone_url
        },
        "local_invoke": True
    }

    # Create a lambda client. This client will inherit the IAM roles defined for the function
    lambda_client = boto3.client('lambda')

    # Using the webhook_function env variable we call a function by name with the webhook mock
    # that we built above. We log the entire response for ease of debugging later, but don't 
    # really have anything to do with it.
    invoke_response = lambda_client.invoke(FunctionName=webhook_function,
                                            Payload=json.dumps(payload))
    logger.info(invoke_response)
    return

