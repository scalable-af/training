# Lab 2.1 - Install AWS SAM and deploy a test function

- Install the AWS SAM CLI.
- Create a function from a template using the CLI.
- Deploy the function using the CLI.
- Get the API Endpoint and test the function


## Steps

1. Install the AWS SAM CLI
    - There are multiple ways you can install the CLI depending on what OS you are running and if you prefer to use a brew based package manager.
    - We will use the pip method for linux systems but if you would like to consider another method such as linuxbrew or if you are using a mac use this link for instructions: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-reference.html

    
        ```bash
        pip install --user aws-sam-cli
        ```
    - Close and re-open your terminal and then run
        ```sh
        sam --version
        ```
        to validate your installation. You should see something similar to:
        ```sh
        SAM CLI, version 0.16.1
        ```
2. Initialize a hello-world function and template
    - Similar to most other frameworks currently (development and otherwise) you can create a simple boiler plate function and template using the CLI to get you started quickly.
    Make sure you are in the folder where you want your code and template file to be created before running this command. It will create a `sam-app` folder wherever it is ran.
    - Initialize a `python 3.7` function and template
        ```sh
        sam init --runtime python3.6
        ```
        you should see something similar to
        ```sh
        2021-01-01 09:49:12 Generating grammar tables from /usr/lib/python3.6/lib2to3/Grammar.txt
        2021-01-01 09:49:12 Generating grammar tables from /usr/lib/python3.6/lib2to3/PatternGrammar.txt
        [+] Initializing project structure...

        Project generated: ./sam-app

        Steps you can take next within the project folder
        ===================================================
        [*] Invoke Function: sam local invoke HelloWorldFunction --event event.json
        [*] Start API Gateway locally: sam local start-api

        Read sam-app/README.md for further instructions

        [*] Project initialization is now complete

        ```
3. Now we will package and deploy our SAM application, starting in the `sam-app` folder that was created.
    - We need a `S3 bucket` where we can upload our Lambda functions packaged as ZIP before we deploy anything 
        ```bash
        aws s3 mb s3://{YOUR_BUCKET_NAME e.g. student00-sam-deploy}
        ```

    - Package our Lambda function and upload it to S3

        ```bash
        sam package \
            --output-template-file packaged.yaml \
            --s3-bucket {YOUR_BUCKET_NAME}
        ```
        You should see output similar to
        ```bash
        Uploading to 7ed8c1a494046a0eb4d0a8068bdb719a  1897 / 1897.0  (100.00%)
        Successfully packaged artifacts and wrote output template to file packaged.yaml.
        Execute the following command to deploy the packaged template
        aws cloudformation deploy --template-file /home/user/source/sam-app/packaged.yaml --stack-name <YOUR STACK NAME>

        ```

    - Create a CloudFormation Stack and deploy our SAM application - this can take a minute or two.
        - Stack names have to be unique per account
        - CAPABILITY_IAM will implicitly create any IAM roles that are required. 

        ```bash
        sam deploy \
            --template-file packaged.yaml \
            --stack-name {YOUR_SAM_APP e.g. student00-sam-app} \
            --capabilities CAPABILITY_IAM
        ```
        You should see something similar to
        ```bash
        Waiting for changeset to be created..
        Waiting for stack create/update to complete
        Successfully created/updated stack - student00-sam-app

        ```
4. Get our API Endpoint
    - We can query CloudFormation to get the resources it created. Specifically the endpoint for the function from the API Gateway.
    ```bash
    aws cloudformation describe-stacks \
        --stack-name student00-sam-app \
        --query 'Stacks[].Outputs[?OutputKey==`HelloWorldApi`]' \
        --output table
    ``` 
    You should see something similar to
    ```bash
    ---------------------------------------------------------------------------------------
    |                                   DescribeStacks                                    |
    +-------------+-----------------------------------------------------------------------+
    |  Description|  API Gateway endpoint URL for Prod stage for Hello World function     |
    |  OutputKey  |  HelloWorldApi                                                        |
    |  OutputValue|  https://qi6hruscbg.execute-api.us-east-2.amazonaws.com/Prod/hello/   |
    +-------------+-----------------------------------------------------------------------+

    ```

# Congratulations you have just deployed your first application and API gateway with AWS SAM