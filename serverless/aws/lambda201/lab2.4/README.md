# Lab 2.4 - Install Serverless Framework and deploy a test function

- Install the Serverless Framework CLI
- Create a function from a template using the CLI
- Deploy the function using the CLI

## Steps

1. Install NPM if you don't have it already.
2. Install serverless
    - We can install serverless using NPM
        ```bash
        sudo npm -g install serverless
        ```
3. We will use the application in our source folder but if you wanted to pull a new application template you can do it with serverless create.
    ```bash
    serverless create --template aws-python3 --path hello-world
    ```
4. We have modified the template to include an API Gateway out of the box already, now we just need to deploy it.
    - From the `source/serverless/hello-world` directory run serverless deploy. Note unlike SAM we didn't have to package it and deploy it. Serverless does it all in one command.
        ```bash
        serverless deploy
        ```
        You should see something similar to
        ```bash
        Serverless: Packaging service...
        Serverless: Excluding development dependencies...
        Serverless: Creating Stack...
        Serverless: Checking Stack create progress...
        .....
        Serverless: Stack create finished...
        Serverless: Uploading CloudFormation file to S3...
        Serverless: Uploading artifacts...
        Serverless: Uploading service hello-world.zip file to S3 (390 B)...
        Serverless: Validating template...
        Serverless: Updating Stack...
        Serverless: Checking Stack update progress...
        ...............................
        Serverless: Stack update finished...
        Service Information
        service: hello-world
        stage: dev
        region: us-east-1
        stack: hello-world-dev
        resources: 10
        api keys:
        None
        endpoints:
        GET - https://fbq36a9yv5.execute-api.us-east-1.amazonaws.com/dev/hello
        functions:
        hello: hello-world-dev-hello
        layers:
        None
        ```
# Congratulations. You have just deployed a hello world application using Serverless