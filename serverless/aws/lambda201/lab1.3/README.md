# Lab 1.3 - Call a Lambda function on commit to master

- You will need your own GitHub account. Use an existing one or create a new one.
- We will be using a public repo to host our blog content.
- The first thing we need to do is get GitHub talking to our Lambda functions, we will use an API gateway for this.
- In this Lab, we are only interested in getting the communication working, we won’t be doing anything with the call from the webhook except logging it.

We will begin creating the building blocks of our static site that will be automatically updated when commits are pushed to the master branch. The source code is in the `source` folder. _Note: Subsequent labs will build on the code in this folder, adding files, refactoring code, and adding new code to existing files._ Be sure to pay careful attention to the changes made in the `source` folder.

## Steps

1. ### First, we need to create our function and the API gateway that will receive be called by the Github webhooks
    - In the sources folder there is a file named `webhook.py` this will be our primary handler for the webhook.
2. ### Let's take a look through this file before we create our function so we understand what it is doing.

    First, we import some packages that we will need later in the code and set up a standard logger. We're creating a logger so that our debugging information is sent to CloudWatch in a format that is more reader-friendly than raw `print` statements.

    ```python
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
    ```

    In a real implementation the `branch_name` variable might be dynamic, but for our purposes, we know we will only be triggering on commits to master. In a larger environment, you might have different functions of logic depending on the branch that you were receiving a webhook for.

    ```python
    branch_name = "master"
    ```

    This is the function we will use as the primary handler for this Lambda function. When seting up the Lambda function's handler, __remember that the file name is on the left side, and the function name is on the right.__ This can be named whatever you want, but descriptive names are best if you plan to re-use your functions. 

    For RESTful APIs, a common pattern for naming is to use the matching HTTP verb. We are consuming a webhook `POST` and invoking our function in one place locally, so we will call this function `post` inside of our Lambda function. When we register this function with Lambda, the __Handler__ will be registered as `webhook.post`.

    ```python
    def post(event, context):
        # Logging the entire event is a cheap simple way to make debugging easier
        # Often times just being able to see the event information quickly can help
        # Troubleshoot an issue faster than hooking up a debugger
        logger.info(event)

        # Here we take a few steps to get the JSON into the body object
        # If this came in as a proxy request, or a direct API Gateway request
        # or a boto3 invokation the format of the body could be a few different types
        # With this stepped approach we can guarantee that no matter how this was called
        # we will have JSON in the body variable.
        if "body" in event:
            body = json.loads(event['body'])
        else:
            try:
                body = json.loads(event)
            except:
                body = event
    ```

    Short-circuiting is an important pattern in Lambda. In traditional infrastructure, customer experience is the most important factor to consider, and wasted cycles that don't impact the customer don't typically matter much. With Lambda, however, every 100ms of time is billed, so anything we can do to preserve those cycles is worth doing.

    Here, we are checking to make sure the webhook from GitHub actually has the information we need in it. We will check to see if the environment variable is set, and that this is a valid request from Github (we will discuss setting that up shortly).

    We are only picking a few pieces out of the payload that we need, but the full documentation for Github webhooks is available if you'd like more information about the rest of the payload. Read more here: [https://developer.github.com/v3/activity/events/types/#pushevent](https://developer.github.com/v3/activity/events/types/#pushevent)

    ```python
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
            raise Exception('Github secrets not defined. Set the environment variable for the function')
    ```

    We only care about push events, so we can validate that with the `X-GitHub-Event` header, and gracefully end execution if it's not the right event type.

    ```python
        if "headers" in event and "X-GitHub-Event" in event['headers']:
            # We only care about push events, if this isn't one politely exit
            if event['headers']['X-GitHub-Event'] != "push":
                return {
                    "statusCode": 200,
                    "body": json.dumps('Skipping - Not a push event')
                }
    ```

    We split the `apikeys` environment variable because we could be re-using this function for multiple API endpoints, multiple repos, etc. It is best practice to have a secret per repo, so even if we use this exact endpoint we can still feed it multiple repos with multiple keys.

    - We define each key with a `,` to separate them.
    - Compute out the hash and validate the signature.
    - If it passes, set secure to `True`. Otherwise, throw an error.

    This way, we know we are getting a payload from Github and that we are being told to pull the right repo. If we didn't validate with the secret, someone could deface our website by simply giving us a different repo to deploy.

    ```python

        apikeys = github_secrets.split(',')

        # set a validation key, we will check multiple keys so it holds our result
        secure = False


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
    ```

    We have to return a status code, otherwise the API Gateway will give a server error. We are likely exceeding the 29s hard timeout limit on the API gateway, but if we can return a response correctly we should attempt to, as that window could be changed later or we could execute in time occasionally.

    ```python
        repo_name = full_name + '/branch/' + branch_name

        return {
                "statusCode": 200,
                "body": json.dumps('Successfully handled %s' % repo_name)
        }
    ```

    Now that we have a basic idea of what the code is doing, we can talk about the individual components and what they mean. We mentioned a few things in the code analysis that we haven't covered yet. We will discuss them as we build them.

3. ### Zip or function up and deploy it to Lambda. 
    *Use a descriptive name, as we create more of these it will be hard to keep track of what is what. `studentID-github-webhook` would work well. Be sure to use your own student ID.*

    *Use the Execution role that we created in lab 1.2, we will be adding to this role throughout the rest of the course.*

    Zip up the function in `webhook.py` that you can find in [/lab1.3/source/](./source/).

    ```bash
    zip -r function.zip .
    ```

    Create that Lambda function with the AWS CLI with the command:

    ```bash
    aws lambda create-function --function-name {FUNCTION_NAME - ex. student00-github-webhook} \
    --zip-file fileb://function.zip --handler webhook.post --runtime python3.7 \
    --role arn:aws:iam::{AWS_ACCOUNT_ID}:role/{EXECUTION_ROLE_FROM_LAB1.2}
    ```

    You should get a json formatted output similar to the below, just like we did in lab 1.2.

    ```json
    {
        "TracingConfig": {
            "Mode": "PassThrough"
        },
        "CodeSha256": "ugE+3+kfQiZZumQHFJxyy7yTxErtzAX8kiT4tgfLQ7M=", 
        "FunctionName": "student00-github-webhook", 
        "CodeSize": 4415, 
        "RevisionId": "e2822df2-2450-42d4-90a8-c6e7bf0b79e0", 
        "MemorySize": 128, 
        "FunctionArn": "arn:aws:lambda:us-east-2:1234567890:function:student00-github-webhook", 
        "Version": "$LATEST", 
        "Role": "arn:aws:iam::1234567890:role/student00-lambda-cli-role", 
        "Timeout": 3, 
        "LastModified": "2019-05-12T12:22:51.690+0000", 
        "Handler": "webhook.post", 
        "Runtime": "python3.7", 
        "Description": ""
    }
    ```

# Create our Github repo, add, and test the Webhook

4. ### We have our function, but we can't publicly access it yet. We need to add an API Gateway. 
    - In the Lambda management console, click on the function.
    - The left hand side shows triggers that are available. Click on the `API Gateway`.
    - You will notice it says configuration is required. If you click on the `API Gateway` that is listed below your function the window area below will show you the `API Gateway` configuration section.
    - Under **Pick an existing API, or create a new one.**, select `Create a new API`.
    - Under **Security** select `Open`, since we need a public service to be able to post to this API we are building.
    - Under **Additional Settings**, you can change the name of the API if you would like to. Otherwise, it will create a name based off of the function name. Either way is fine, and it won't change how we interact with the API in any way.
    - After you click on **Add**, your changes aren't saved yet. You will see that the **API Gateway** shows `Unsaved changes`.
    - Click on **Save** in the upper right hand corner of the page to save your function, including the API endpoint we have configured for it.
    - Clicking on the **API Gateway** now will show its configuration information, including an **API Endpoint** below the API name at the bottom of the screen.
    - Copy the `API Endpoint` value, we will need it for our Github webhook.
    - By default configuring an API Gateway in this manner, we have set up a `Lambda Proxy`, meaning that all request types are passed through to the Lambda function. This is the easiest way to get started with a function, and will work for almost all RESTful functions. If you want to call different functions based on different HTTP verbs, you can do that, or you can handle that logic in your function.

5. ### Setup our GitHub repository to emit a webhook.
    - Create a new public GitHub repo. We will use it for our blog, so give it an appropriate name.
    - When you create a new empty repo Github will show you a page suggesting various ways to initialize your repository. We don't have a blog folder yet but we will soon. For now follow the steps for creating a new repository from the command line. Create a folder, `git init` the folder, modify a file, commit it, and add the remote **but do not push it yet - we will use this initial push for our test of the webhook**
    - On the top right click on **Settings**.
    - There is an option labeled **Webhooks** on the left menu, select that.
    - Click on **Add Webhook**.
    - Under the **Payload URL** paste in the `API Endpoint` we copied from when we made the **API Gateway**.
    - Change the content type to `application/json` (The API Gateway really doesn't handle form data well.)
    - Set a **Secret**. This can be anything, a simple string will be fine for now. We will need to save this and set it as an environment variable on our function to validate the authenticity of messages as we saw when reviewing the code. **Remember the secret you set here - you will need it for lab 1.4**
    - Under `Which events would you like to trigger this webhook?` You can leave just the push event selected. That is all we really care about for this. More often than not that is what you will use, hence it being the default.
    - Make sure `Active` is selected.
    - Click on **Add Webhook**.
        ![Github Secrets](./images/github.jpg "Github Secrets")
    - Now that we have our webhook in place, we are ready to do the push that we skipped when creating our repo earlier.
    - From within the folder that you initialized for our blog run:

    ```sh
    git push -u origin master
    ```

6. ### We can validate our function works and logged the push event properly.
    - In the Lambda management console, click on your webhook function.
    - On the top-left of the page, click on the tab labeled **Monitoring**.
    - On the right hand side, click on the button to **View logs in CloudWatch**. This will take you to the logs for this particular function in CloudWatch.
    - You will see the alias, in this case $LATEST (the default), followed by a hash.
        - _Each time you make any changes to your function, a new hash will be generated. If you are wanting to look at the logs for a function you can look at the latest hash, and subsequent runs will be added to that stream. If you change the function, a new stream and a new hash will be made, so you have to be sure to look at the latest one._
    - Click on the latest stream.
    - You can expand the individual lines, you should see a line that outputs the `event` containing our webhook post information. This can be a bit hard to read but there are many applications and methods for formatting the output in a more readable manner.
    - It may take a few seconds for the log to show up in CloudWatch. Click the refresh icon at the top-right of the log output to refresh the view.

## Congratulations! You have successfully triggered a Lambda function from a commit on the master branch of a Github repo.
