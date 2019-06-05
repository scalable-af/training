from __future__ import print_function # Python 2/3 compatibility
import boto3
import json
import decimal
import uuid
import logging
import os

# Setup our standard logger. We re-use the same format in most places so we have a standard presentation
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers[0].setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))


# Firefox sends an OPTIONS request before sending a POST requestion
# We have to respond with the below information of Firefox will never send the POST
# This could also be configured in the API gateway.
# Since Firefox is particular about this we will use a wrapper for all of our responses
# to make it a non-issue for anything we are trying to do.
# If would be more secure to define the specific domains that could call/add comments
# but we don't know what those domains will be currently
def cors_response(message, status_code):
    return {
        'statusCode': str(status_code),
        'body': json.dumps(message),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, X-Experience-API-Version,Authorization',
            'Access-Control-Allow-Methods': 'POST, OPTIONS, GET, PUT'
            },
        }

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

# Perform a scan operation on table. 
# Can specify filter_key (col name) and its value to be filtered. 
# This gets all pages of results. Returns list of items.
# This is the only way to get all of the items match our particular page
# without having to create a secondary index.
# We also have to do this because we used a UUID for the primary key in our table
# We did that so people with the same name can leave a comment, or someone can leave more than one comment
# If we had used the name or email, they would only be able to leave a single comment
def scan_table_allpages(table, filter_key=None, filter_value=None):
    if filter_key and filter_value:
        filtering_exp = boto3.dynamodb.conditions.Key(filter_key).eq(filter_value)
        response = table.scan(FilterExpression=filtering_exp)
    else:
        response = table.scan()

    items = response['Items']
    while True:
        if response.get('LastEvaluatedKey'):
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items += response['Items']
        else:
            break

    return items

# This can be named whatever you want but a descriptive name is best if re-using functions
# A common pattern is to use the matching HTTP verb for a RESTful API
def post(event, context):

    # Logging the entire event is a cheap simple way to make debugging easier
    # Often times just being able to see the event information quickly can help
    # Troubleshoot an issue faster than hooking up a debugger
    logger.info(event)

    # Short circuit if this is a Firefox pre-flight OPTIONS check
    if event['httpMethod'] == "OPTIONS":
        logger.info("Allowing CORS")
        return cors_response({"message": "allowed"}, 200)
 
    logger.info(event['queryStringParameters'])
    if "httpMethod" in event and event['httpMethod'] == "GET":
        if "page" in event['queryStringParameters']:
            try: 
                event_json=json.loads(event['queryStringParameters'])
            except:
                event_json=event['queryStringParameters']
    else: 
        # Here we take a few steps to get the JSON into the event_json object
        # If this came in as a proxy request, or a direct API Gateway request
        # or a boto3 invokation the format of the body could be a few different types
        # With this stepped approach we can gaurantee that no matter how this was caled
        # we will have JSON in the event_json variable.
        if "body" in event:
            try:
                event_json=json.loads(event['body'])
            except:
                pass
        else:
            try:
                event_json=json.loads(event)
            except:
                event_json=event

    # Short circuit to save time if we don't have any of the critical data
    try:
        page = event_json['page']
    except:
        raise Exception('page not found in submission')

    try:
        name = event_json['name']
    except:
        raise Exception('name not found in submission')

    try:
        comment = event_json['comment']
    except:
        raise Exception('comment not found in submission')

    try:
        table_name = os.environ['table_name']
    except:
        raise Exception('DynamoDB table for comments not defined. Set the environment variable for the funcion')

    
    # Setup our connection to dynamoDB
    # This is a boto3 "resource" the Lambda interactions that we do are a "client" type
    # It is important to notice that distinction otherwise it will error when trying
    # to initiate the setup
    dynamodb = boto3.resource('dynamodb')
    try:
        table = dynamodb.Table(table_name)
    except:
        raise Exception('unable to connect to table for comments')


    # Put our comment into the table. We use a UUID for the primary key so the same name
    # can make multiple comments, otherwise it would be over-written every time
    response = table.put_item(
    Item={
            'uuid': str(uuid.uuid4()),
            'name': name,
            'comment': comment,
            'page': page
            }
    )

    # Logging is essentially free, log as much as possible, it saves troubleshooting time
    logger.info("PutItem succeeded:")
    # If you know you are logging JSON specifically it is really nice to specify an indent
    # it makes reading large JSON blobs so much easier.
    logger.info(json.dumps(response, indent=4, cls=DecimalEncoder))

    # Give our CORS compliant response back, and pass a 200 status so the API gateway is happy
    return cors_response({"message": 'Comment added for %s' % page}, 200)

# In the same file we are setting up another Lambda handler
# We have a bunch of things in common with the other function so instead of
# duplicating all of that code we can create another function and setup an 
# additional lambda pointing to this function as the entry point
# We can use this pattern to compose fairly large projects without code duplication
# or having hundreds of zip files that are impossible to manage

# This can be named whatever you want but a descriptive name is best if re-using functions
# A common pattern is to use the matching HTTP verb for a RESTful API
def get(event, context):

    # Logging the entire event is a cheap simple way to make debugging easier
    # Often times just being able to see the event information quickly can help
    # Troubleshoot an issue faster than hooking up a debugger
    logger.info(event)

    # If it unlikely this is getting called by the webapp because we are
    # injecting into the markdown directly but by setting this
    # we could switch to rendering the comments on the page with JS if we wanted to
    # without having to change the function
    if "httpMethod" in event and event['httpMethod'] == "OPTIONS":
        logger.info("Allowing CORS")
        return cors_response({"message": "allowed"}, 200)
    
    if "queryStringParameters" in event:
        logger.info(event['queryStringParameters'])
    if "httpMethod" in event and event['httpMethod'] == "GET":
        if "page" in event['queryStringParameters']:
            try: 
                event_json=json.loads(event['queryStringParameters'])
            except:
                event_json=event['queryStringParameters']
    else: 
        # Here we take a few steps to get the JSON into the event_json object
        # If this came in as a proxy request, or a direct API Gateway request
        # or a boto3 invokation the format of the body could be a few different types
        # With this stepped approach we can gaurantee that no matter how this was caled
        # we will have JSON in the event_json variable.
        if "body" in event:
            try:
                event_json=json.loads(event['body'])
            except:
                pass
        else:
            try:
                event_json=json.loads(event)
            except:
                event_json=event

    # Short circuit to save time if we don't have any of the critical data
    try:
        page = event_json['page']
    except:
        raise Exception('page not found in submission')

    try:
        table_name = os.environ['table_name']
    except:
        raise Exception('DynamoDB table for comments not defined. Set the environment variable for the funcion')
    
    
    # Setup our connection to dynamoDB
    # This is a boto3 "resource" the Lambda interactions that we do are a "client" type
    # It is important to notice that distinction otherwise it will error when trying
    # to initiate the setup
    dynamodb = boto3.resource('dynamodb')
    try:
        table = dynamodb.Table(table_name)
    except:
        raise Exception('unable to connect to table for comments')

    # Use our scan function to return a list of all the comments
    # for a particular page that we are processing
    items = scan_table_allpages(table, "page", page)
    logger.info(items)

    modified_items = []
    for item in items:
        modified_items.append({
            "name": 'Name: {}\n'.format(item["name"]),
            "comment": item["comment"]
        })


    # If we find any comments return with the appropriate status code
    if items:
        return cors_response(modified_items, 200)
    # If not items are found use the appropriate HTTP code
    # In our local invokation of this in the webhook we aren't using the status
    # code we are counting the items that are returned but if this were being
    # called by a JS handler on the page we would need to use the status code
    # So it makes sense to future proof and return appropriately for both scenarios
    else:
        return cors_response([], 404)