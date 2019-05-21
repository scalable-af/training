import os
import stat
import shutil
import logging
import hmac
import hashlib
import json

# Setup our standard logger. We re-use the same format in most places so we have a standard presentation
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers[0].setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))

# In a real implementation this would be dynamic but we know we are only triggering
# on master. In a larger environment you might have different functions of logic
# depending on the branch that you were receiving a webhook for.
branch_name = "master"

# This can be named whatever you want but a descriptive name is best if re-using functions
# A common pattern is to use the matching HTTP verb for a RESTful API
# We consume a webhook post, and a local invokation but we will just call this post.
def post(event, context):
    # Logging the entire event is a cheap simple way to make debugging easier
    # Often times just being able to see the event information quickly can help
    # Troubleshoot an issue faster than hooking up a debugger
    logger.info(event)

    # Here we take a few steps to get the JSON into the body object
    # If this came in as a proxy request, or a direct API Gateway request
    # or a boto3 invokation the format of the body could be a few different types
    # With this stepped approach we can gaurantee that no matter how this was caled
    # we will have JSON in the body variable.
    if "body" in event:
        body = json.loads(event['body'])
    else:
        try:
            body = json.loads(event)
        except:
            body = event
 
    # We will still validate this before doing anything with it, but if we are missing
    # any essential components we should end early to save processing time.
    # No point in computing hashes for a payload that is missing data we need.
    try:
        full_name = body['repository']['full_name']
    except KeyError:
        raise Exception('Failed to find full_name in json post body')

    try:
        remote_url = body['repository']['clone_url']
    except KeyError:
        raise Exception('Failed to find clone_url name in json post body')

    try:
        github_secrets = os.environ['github_secrets']
    except:
        raise Exception('Github secrets not defined. Set the environment variable for the funcion')

    if "headers" in event and "X-GitHub-Event" in event['headers']:
        # We only care about push events, if this isn't one politely exit
        if event['headers']['X-GitHub-Event'] != "push":
            return {
                "statusCode": 200,
                "body": json.dumps('Skipping - Not a push event')
            }

    # We split this env variable because we could be re-using this function for multiple API
    # endpoints, multiple repos etc. It is best practice to have a secret per repo
    # so even if we use this exact endpoint we can still feed it multiple repos with multiple
    # keys. We define each key with a , to separate them.
    apikeys = github_secrets.split(',')

    # set a validation key, we will check multiple keys so it holds our result
    secure = False

    # Compute out the hash and validate the signature. If it passes set secure, otherwise throw an error
    if 'X-Hub-Signature' in event['headers'].keys():
        signature = event['headers']['X-Hub-Signature']
        for k in apikeys:
            computed_hash = hmac.new(k.encode('ascii'), event['body'].encode('ascii'), hashlib.sha1)
            computed_signature = '='.join(['sha1', computed_hash.hexdigest()])
            hmac.compare_digest(computed_signature.encode('ascii'), signature.encode('ascii'))
            if hmac.compare_digest(computed_signature.encode('ascii'), signature.encode('ascii')):
                secure = True
    if secure == False:
        raise Exception('Failed to validate authenticity of webhook message')
    
    repo_name = full_name + '/branch/' + branch_name
    # We have to return a status code otherwise the API Gateway will give a server error
    # however we are likely exceeding the 29s hard timeout limit on the API gateway
    # but if we can return correctly we should attempt to, that window could be changed later
    # or we could execute in time occassionally
    return {
            "statusCode": 200,
            "body": json.dumps('Successfully handled %s' % repo_name)
    }
