# Lab 1.5 - Adding comments to our static site

We are going to add dynamic functionality to our static site using Lambda functions and DynamoDB. We will also use DynamoDB events to trigger rebuilds of our site when new comments are submitted. Our site will remain 100% static, and fully automated.

- We will use a lambda function to:
    - Receive form submissions.
    - Add them to a Dynamo DB table.
    - Trigger a rebuild when new entries are made in the DynamoDB
    - Inject our comments into our posts before they are compiled and uploaded.

## Steps

1. First, let's look at all of the new code we will be using to enable this functionality. We have two new files and a modification to our existing webhook.
    - `comment.py` will handle posting and getting our comments.
    - `dynamo_stream.py` will trigger a rebuild when a DynamoDB event is fired.
    - `webhook.py` has a few changes to facilitate pulling new comments into the build process.

    We will start with `comments.py`.

    *Note: We will only cover code that we have not seen before, or that provides specific functionality.*

    Firefox sends an `OPTIONS` request before sending a `POST` request. We have to respond with the below information or Firefox will never send the POST. (This could also be configured in the API gateway.) Since Firefox is particular about this, we will use a wrapper for all of our responses to make it a non-issue for anything we are trying to do. It would be more secure to define the specific domains that could call/add comments, but we don't know what those domains will be currently.

    ```python
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
    ```

    Perform a `scan` operation on table. We can specify `filter_key` (col name) and the value to be filtered. This will return all pages of results as a list of items. This is the only way to get all of the items that match our particular page without having to create a secondary index. Additionally,  we have to do this because we used a UUID for the primary key in our table. We did that so people with the same name can leave a comment, or someone can leave more than one comment. (If we had used the name or email, they would only be able to leave a single comment.)

    ```python
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
    ```

    Here we set-up our connection to DynamoDB. This is a boto3 `resource`, and the Lambda interactions that we do are a `client` type. It is important to notice of that distinction, otherwise it will error when trying to initiate the setup.

    ```python
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
    ```

    Logging is essentially free. Log as much as possible, as it can save you troubleshooting time later.

    ```python
    logger.info("PutItem succeeded:")
    # If you know you are logging JSON specifically it is really nice to specify an indent
    # it makes reading large JSON blobs so much easier.
    logger.info(json.dumps(response, indent=4, cls=DecimalEncoder))
    ```

    This is the first time we will have two handlers in the same file. We will use this same file, and `function.zip` to run two different Lambda functions. We have a `post` function that receives and stores the comments and a `get` function that will output comments to our webhook for loading them into the static site. Via the __API Gateway__, we could register two different verbs on the same path that go to two different functions, but we will only be calling our `get` function from another internal function--so we don't need to worry about routing it.

    We put both functions in the same file because they have similar patterns and have functions in common. There is no need to duplicate all of that code to create isolated functions. You can develop applications into logical units that re-use code while still being manageable, but that are also abstracted enough to be used in serverless architectures. There is only a small amount of new code in this function as a result of that. Most of the file has been omitted here because it has all been covered previously.

    ```python
    def get(event, context):
        ...

        # If we find any comments return with the appropriate status code
        if items:
            return cors_response(items, 200)
        # If no items are found use the appropriate HTTP code
        # in our local invocation of this in the webhook we aren't using the status
        # code we are counting the items that are returned but if this were being
        # called by a JS handler on the page we would need to use the status code
        # So it makes sense to future proof and return appropriately for both scenarios
        else:
            return cors_response([], 404)
    ```

    Now we will take a look at `dynamo_stream.py`.

    We are going to emulate the few bits we need to fire off the building of our Hugo site. We will effectively fake the webhook. On the other side, we check to see if this is working from the mocked stream handler, and if it is, we do fewer checks for validity. This function is well documented and fairly brief, so we will review it in its entirety.

    ```python
    def fake_webhook(event, context):
        # We take in an event, that is the DynamoDB change event, but since we are building
        # a static site that has to be compiled completely, we aren't doing anything with it.
        # We are just using it as a trigger for an event that rebuilds the whole site.
        # There are better and less wasteful ways to do something like, this but it works well
        # for demonstrating how a stream event can be used as a generic trigger.

        # We need the full name of the repo. We can see this in the webhook that we logged in lab 1.3.
        try:
            full_name = os.environ['full_name']
        except:
            raise Exception('Full Name not defined. Set the environment variable for the function')

        # We need the HTTPS clone_url, we can see this in the webhook that we logged in lab 1.3.
        try:
            clone_url = os.environ['clone_url']
        except:
            raise Exception('Clone URL not defined. Set the environment variable for the function')

        # For modularity, we don't bake in the name of the GitHub processing webhook, and instead specify it via env variable.
        try:
            webhook_function = os.environ['webhook_function']
        except:
            raise Exception('Webhook Function not defined. Set the environment variable for the function')

        # Build our payload, using the same structure and the essential items from the real GitHub webhook.
        # Set a flag indicating that this payload is from another lambda function so that we can short
        # circuit some of our conditional login in the webhook and re-use the same function.
        payload = {
            "repository": {
                "full_name": full_name,
                "clone_url": clone_url
            },
            "local_invoke": True
        }

        # Create a Lambda client. This client will inherit the IAM roles defined for the function.
        lambda_client = boto3.client('lambda')

        # Using the `webhook_function` env variable, we call a function by name with the webhook mock
        # that we built above. We log the entire response for ease of debugging later, but don't
        # really have anything to do with it.
        invoke_response = lambda_client.invoke(FunctionName=webhook_function,
                                                Payload=json.dumps(payload))
        logger.info(invoke_response)
        return
    ```

    We also have one new function in our `webhook.py`  
    This function calls our comments.get function to receive a list of comments based on the page name we are processing. Then it appends the comments in a standard markdown format before the site is compiled to static content.

    ```python
    def add_comments(local_path, comment_function):
    lambda_client = boto3.client('lambda')
    # r=root, d=directories, f = files
    for r, d, f in os.walk(local_path):
        for file in f:
            # We only care about md files as those are posts we will inject into
            if '.md' in file:
                # We are setting this as a short circuit. We only want to look for
                # comments if the post has an appropriate comments section
                # this saves us lambda invokations for posts or files that don't have it
                show_comments = False
                file_name = file.split('.')[0]
                file_path = os.path.join(r, file)
                with open(file_path, 'r') as searchfile:
                        for line in searchfile:
                            if '### Comments' in line:
                                show_comments = True
                if show_comments:  
                    invoke_response = lambda_client.invoke(FunctionName=comment_function,
                                            Payload=json.dumps('{"page": "' + file_name + '"}'))
                    lambda_response = json.loads(invoke_response['Payload'].read())
                    comments = json.loads(lambda_response["body"])
                    logger.info(comments)
                    # Make sure we actually have some comments to write before trying to touch the file
                    if len(comments) > 0:
                        with open(file_path, 'a') as postfile:
                            # We inject the comments as simple unordered lists at the end of the file
                            # This is really brittle and requires writing our posts in a specific way
                            # but it works well for this lab
                            for comment in comments:
                                postfile.write('- {}\n'.format(comment["name"]))
                                postfile.write('  - {}\n'.format(comment["comment"]))
    ```
    One thing to note is that we are using `### Comments` to determine if we inject comments or not. If a post is created but doesn't have that comments won't be added. Additionally if that is not at the end of the file comments will not show up in the best place. This could be designed in a number of ways that would be more resilient but it will work well for our demonstration and shows how you can make legacy or static systems tolerate serverless components. Also not that we are determining what `comment_function` to run using an environment variable. Trying to provide as much potential re-use as possible.

2. Create our three new functions
    - `studentID-comments-post` to receive our comments and put them into the DynamoDB table.

        ```bash
        aws lambda create-function --function-name {FUNCTION_NAME - ex. student00-comments-post} \
        --zip-file fileb://function.zip --handler comments.post --runtime python3.7 \
        --role arn:aws:iam::{AWS_ACCOUNT_ID}:role/{EXECUTION_ROLE_FROM_LAB1.2}
        ```

    - `studentID-comments-get` to return all the comments matching our page for `github-webhook` to compile the comments into the static files.

        ```bash
        aws lambda create-function --function-name {FUNCTION_NAME - ex. student00-comments-get} \
        --zip-file fileb://function.zip --handler comments.get --runtime python3.7 \
        --role arn:aws:iam::{AWS_ACCOUNT_ID}:role/{EXECUTION_ROLE_FROM_LAB1.2}
        ```

    - `studentID-dynamo-stream` to be triggered any time changes are made to the DynamoDB, calling the github-webhook with a mocked payload to trigger a rebuild of the static content. This way our comments are updated automatically without us having to do anything. Even if we go in the table and manually remove/moderate them.

        ```bash
        aws lambda create-function --function-name {FUNCTION_NAME - ex. student00-dynamo-stream} \
        --zip-file fileb://function.zip --handler dynamo_stream.fake_webhook --runtime python3.7 \
        --role arn:aws:iam::{AWS_ACCOUNT_ID}:role/{EXECUTION_ROLE_FROM_LAB1.2}
        ```

3. Create an `API Gateway` for our `studentID-comments-post` function
    - You can create an `API Gateway` via the CLI, but it is a long drawn out process that we will simply be using the SAM/Serverless frameworks for tomorrow. For simple services and applications, using the UI works well. Create an `API Gateway` for your `studentID-comments-post` function similar to what you did in lab 1.3 when setting up the initial webhook.

4. Configure the blog to submit comments to our function
    - Copy the `API Endpoint` and put it in the `config.toml` file in the root directory of your blog. Replace the following line

        ```toml
        [params.lambdaComments]
        endpoint = "http://the-url-to-our-lambda-API-Gateway"
        ```

5. Create our comments DynamoDB table
    - Use the CLI to create a table. We are creating a table with a primary index of `uuid` so we can have multiple comments from the same people. We set it to a single read/write capacity unit to keep the cost down as it is highly unlikely we will need much throughput capacity on our table.
        ```sh
        aws dynamodb create-table --table-name {YOUR_TABLE_NAME e.g. studentID-comments} --attribute-definitions AttributeName=uuid,AttributeType=S --key-schema AttributeName=uuid,KeyType=HASH --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1
        ```
        Output should look similar to the following
        ```json
        {
            "TableDescription": {
                "AttributeDefinitions": [
                    {
                        "AttributeName": "uuid",
                        "AttributeType": "S"
                    }
                ],
                "ProvisionedThroughput": {
                    "NumberOfDecreasesToday": 0,
                    "WriteCapacityUnits": 1,
                    "ReadCapacityUnits": 1
                },
                "TableSizeBytes": 0,
                "TableName": "student00-comments",
                "TableStatus": "CREATING",
                "KeySchema": [
                    {
                        "KeyType": "HASH",
                        "AttributeName": "Artist"
                    }
                ],
                "ItemCount": 0,
                "CreationDateTime": 1421866952.062
            }
        }
        ```

6. Add our table name to both of our comments functions
    - Set our table name environment variable in both of your `comments` Lambda functions  
        *Note in the below, because we use the {YOUR_VARIABLE} syntax for what needs to be replaced there is two `}}` at the end of the line, but when you put in your name it should look like `"Variables={table_name=student00-comments}" `*  

        *By now you are likely used to the output format for creating and updating functions so we won't include it for review. If you want to confirm it looks like what you are seeing you can refer to one of the previous labs.*

        ```sh
        aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-comments-get} --environment "Variables={table_name={YOUR_TABLE_NAME - e.g. student00-comments}}" 
        ```

        ```sh
        aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-comments-post} --environment "Variables={table_name={YOUR_TABLE_NAME - e.g. student00-comments}}" 
        ```

7. Add all of the environment variables needed to connect our `dynamo-stream` and `github-webhook` functions together
    - We need to add the `webhook_function` environment variable in our `dynamo-stream` function as we saw in the code review earlier, we also need to set the `comment_function` (specifically the function matching the get as this is howe we will read in the comments) environment variable for our `github-webhook` function so they can reference each-other appropriately.  
      

        We also need to add the `full_name` and `clone_url` environment variables to our `dynamo-stream` function. The content for these can be found in the `github-webhook` logs from lab 1.3. Look in the CloudWatch stream for the messages we saved. The `clone_url` will look something like `https://github.com/scalable-af/training.git` and the `full_name` similar to `scalable-af/training`

        ```sh
        aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-dynamo-stream} --environment "Variables={webhook_function={YOUR_WEBHOOK_FUNCTION - e.g. student00-github-webhook},full_name={YOUR_REPO_FULL_NAME},clone_url={YOUR_CLONE_URL}}"
        ```

        ```sh
        aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-github-webhook} --environment "Variables={comment_function={YOUR_COMMENTS_FUNCTION - e.g. student00-comments-get}}"
        ```

8. Update our `github-webhook` code to enable the `add_comments` feature.

    - Now that we have the support functions we can update our `github-webhook` code with the `add_comments` functionality. If we had done it earlier and a commit was made to our blog it would error out. Now we have everything it needs to run even if there are no comments.

        In the `lambda` folder, run:

        ```sh
        rm function.zip && zip -r function.zip .
        ```

        And update your function with the new code:

        ```sh
        aws lambda update-function-code --function-name {FUNCTION_NAME - ex. student00-github-webhook} \
        --zip-file fileb://function.zip
        ```

9. Add an in-line policy for our execution role so that functions can call other functions within our account and to ensure we can access the stream.  
*This is a super open policy, you wouldn't want to use it in production but for testing when adding many new resources it can be useful. Feel free to experiment with making it appropriately restrictive.*

    - Put our policy into a JSON file

    ```sh
    echo '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:*",
                    "dynamodb:*",
                    "lambda:*",
                    "logs:*",
                    "s3:*"
                ],
                "Resource": "*"
            }
        ]
    }' > /tmp/new-policy.json
    ```
    And apply it to your role from lab 1.3
    ```sh
    aws iam put-role-policy --role-name {YOUR_CLI_ROLE - e.g. student00-lambda-cli-role} --policy-name FullAccess --policy-document file:///tmp/new-policy.json
    ```

10. Setup our DynamoDB Table to call our `studentID-dynamo-stream` function when entries are added to the table.

    - Unfortunately there is no way currently to setup a DynamoDB stream via the basic CLI so we will have to use the UI to configure our DynamoDB Table to trigger our `studentID-dynamo-stream` function when anything is added to the table.
    - Go back to the Lambda function editor.
    - Select your `studentID-dynamo-stream` function.
    - Similar to how we added an `API Gateway` from the left hand side select `DynamoDB`
    - It will hae a message saying `Configuration required` click on that.
    - Now at the bottom there is a `Configure triggers` panel.
    - Under `DynamoDB table` select the table that you setup for this.  
        *Since multiple students may be using the same account, be sure to pick your specific table.*
    - Click `Add` in the lower right hand corner
    - Click `Save` on you function in the upper right hand corner



11. Create a comment on your blog and see if the page is automatically rebuilt in a minute or two.

# Congratulations you have enabled dynamic content via event streams and lambda functions.
