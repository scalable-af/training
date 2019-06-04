# Lab 1.4 - Build and deploy a Hugo site on commit

In this lab, we will expand the function from Lab 1.3. We will add a layer for Hugo and a layer for the AWS CLI, so that we can push your static site to a publicly accessible S3 bucket.

- The Hugo layer will compile our site into static HTML.
- The AWS CLI layer will be used to sync the content we generate with the S3 bucket hosting our public site.

Now that we are getting into more advanced usage, the structure of our `sources` folder has changed a bit.

- We now have 3 folders, `blog`, `lambda`, and `layers`
    - `blog` contains the Hugo content. We created a folder for this in the last lab and used a git init to test our Lambda function. In this lab we will add some pre-made hugo content and templates.
    - `lambda` now houses our Lambda function. We are getting to the point where we need to add additional packages and modules. Creating folders for our functions will help keep that tidy.
    - `layers` these are a few pre-compiled layers that we will need for the binaries we plan to run. We could build these ourselves or use ARNs of existing ones, but for the sake of simplicity, we will use pre-made layers. It is pretty common to use pre-made layers, and we will discuss them a bit more in this lab.

## Steps

1. ### Copy the content from [lab1.4/source/blog](./lab1.4/source/blog) to the folder you setup for your blog. 
    _Don't commit or push it yet, just get it there and ready for when we need it. You can do a `git status` to make sure all the files show as new/updated._

2. ### Let's take a look at what is new in the code and why we moved it to a new folder.
    - We have a couple of new imports:
        - We have `pygit2` which will handle all of our repo management. We had to add pygit2 to our source folder because it doesn't come with Lambda by default. You can add additional packages to your source folder using `pip install package_name --target .`, but there could be some complexity if you are using virtual environments or Anaconda. For this lab, we have provided the `lambda` source folder with the necessary modules added in already.
        - We also now have `boto3`. This is the AWS SDK, and you can use this package to interact with AWS services. We don't have to add it to our source because it is included by default in all Python Lambda functions, and therefore we just need to import it to use it.
        - We import `subprocess` a part of the Python core packages. We will be using this to run some of the binaries that we include in our function with the layers mentioned previously.

    ```python
    from pygit2 import discover_repository, Repository, clone_repository, GIT_RESET_HARD
    import boto3
    ...
    import subprocess
    ```

    _Note: We will skip over any lines you have seen before._

    ```python
    # If true the function will delete all files at the end of each run
    cleanup = False

    # The path that we will build hugo into for uploading to S3
    build_path = "/tmp/hugo/public"
    ```

    All of these functions are pretty straight forward. We use them to initialize, create, and pull a GitHub repo. If possible, we want to re-use any existing files on the system to speed up our execution time. Although we are guaranteed to have this container recycled every 4 hours or so, if we can use the cache to build our site faster when the pod is warm, that is a win. We use the functions below to try and initialize an existing repo (or create a new one) and pull any changes to the local file system on the container.

    ```python
    # Initialized a repo, similar to running git init on the command line
    def init_remote(repo, name, url):
        remote = repo.remotes.create(name, url, '+refs/*:refs/*')
        return remote

    # Configured a remote/upstream association. The same as setting a remote on your repo via cli
    def create_repo(repo_path, remote_url):
        if os.path.exists(repo_path):
            logger.info('Cleaning up repo path...')
            shutil.rmtree(repo_path)
        repo = clone_repository(remote_url, repo_path)

        return repo

    # Pull the repo from the remote. Similar to doing a git clone, or git pull via the cli
    def pull_repo(repo, branch_name, remote_url):
        remote_exists = False
        for r in repo.remotes:
            if r.url == remote_url:
                remote_exists = True
                remote = r
        if not remote_exists:
            remote = repo.create_remote('origin', remote_url)
        logger.info('Fetching and merging changes from %s branch %s', remote_url, branch_name)
        remote.fetch()
        if(branch_name.startswith('tags/')):
            ref = 'refs/' + branch_name
        else:
            ref = 'refs/remotes/origin/' + branch_name
        remote_branch_id = repo.lookup_reference(ref).target
        repo.checkout_tree(repo.get(remote_branch_id))
        repo.head.set_target(remote_branch_id)
        return repo
    ```

    _This requires Python 3.5 or above._ `subprocess` runs a command as if it were in the shell, and gives us the standard and error output for logging. We will use this to run commands as if they were in a terminal and be able to log their output.

    ```python
    def run_command(command):
        command_list = command.split(' ')
        try:
            logger.info("Running shell command: \"{0}\"".format(command))
            result = subprocess.run(command_list, stdout=subprocess.PIPE);
            logger.info("Command output:\n---\n{0}\n---".format(result.stdout.decode('UTF-8')))
        except Exception as e:
            logger.error("Exception: {0}".format(e))
            raise e
        return True
    ```

    This builds a Hugo website using the source (the repo) and desination for the public content:

    ```python
    def build_hugo(source_dir, destination_dir,debug=False):
        logger.info("Building Hugo site")
        run_command("/opt/hugo -s {0} -d {1}".format(source_dir,destination_dir))
        run_command("ls -l {0}".format(destination_dir))
    ```

    This uploads the built website to S3. We are using the AWS CLI because it has the sync feature which is a lot faster than doing the same in pure Python. It might seem like an anti-pattern to shell out in a function when you could do the same thing purely in code, but time is money on Lambda, and this is significantly faster than doing a file at a time by walking the directory.

    ```python
    def upload_to_s3(local_path,s3_path):
        logger.info('Uploading Hugo site to S3: {0}'.format(s3_path))
        run_command('/opt/aws s3 rm s3://{0} --recursive'.format(s3_path))
        run_command('/opt/aws s3 sync {0} s3://{1}'.format(local_path,s3_path))
        run_command('/opt/aws s3 ls {0}'.format(s3_path))
    ```

    We always want to take the shortest path through our functions. Check for anything fatal first:

    ```python
    try:
        output_bucket = os.environ['output_bucket']
    except:
        raise Exception('Output Bucket not defined. Set the environment variable for the function')
    ```

    If we have an existing repo (if this function is still warm / is not a cold start,) we can re-use that repo on the file system and update it to save us some time and bandwidth. Once something has been created (or re-used), we now have a repo reference to pull against. If a previous repo is not found, we will create it and then compile the site to our pre-defined path. Once we have the compiled site we use the AWS CLI to run an S3 `sync` command to deploy the static content to our S3 bucket for hosting.

    ```python
    repo_name = full_name + '/branch/' + branch_name
    repo_path = '/tmp/%s' % repo_name

    try:
        repository_path = discover_repository(repo_path)
        repo = Repository(repository_path)
        logger.info('found existing repo, using that...')

    except Exception:
        logger.info('creating new repo for %s in %s' % (remote_url, repo_path))
        repo = create_repo(repo_path, remote_url)

    pull_repo(repo, branch_name, remote_url)
    build_hugo(repo_path, build_path)
    upload_to_s3(build_path, output_bucket)
    ```

    - Copy the code from the `lambda` folder to the folder you have been using for your function from lab 1.3, or start using this folder. You can also manually add the functions in if you want to, but if you get any issues while trying to run it, use the code straight from the examples.

3. ### Zip your function up and **update** the webhook you created in lab 1.3

    In the `lambda` folder, run:

    ```sh
    rm function.zip && zip -r function.zip .
    ```

    And update your function with the new code:

    ```sh
    aws lambda update-function-code --function-name {FUNCTION_NAME - ex. student00-github-webhook} \
    --zip-file fileb://function.zip
    ```

    You should see a response similar to the following:

    ```json
    {
        "FunctionName": "student00-github-webhook",
        "LastModified": "2019-05-20T03:55:32.167+0000",
        "RevisionId": "1bb3ed4e-d0ae-4a19-bbba-bc29fb5a3641",
        "MemorySize": 128,
        "Version": "$LATEST",
        "Role": "arn:aws:iam::1234567890:role/student00-lambda-cli-role",
        "Timeout": 3,
        "Runtime": "python3.7",
        "TracingConfig": {
            "Mode": "PassThrough"
        },
        "CodeSha256": "+GNC3W4kJAcnnZNh1DU3uz8WuPUo3rmhy7v8nsbmTCo=",
        "Description": "",
        "VpcConfig": {
            "SubnetIds": [],
            "VpcId": "",
            "SecurityGroupIds": []
        },
        "CodeSize": 5932697,
        "FunctionArn": "arn:aws:lambda:us-east-2:1234567890:function:student00-github-webhook",
        "Handler": "webhook.post"
    }
    ```

    Notice the `Timeout` listed in the return is the default of 3 seconds. This definitely won't be enough time to download and compile a static HTML website from Github. We need to increase that. The `API Gateway` has a hard limit of 30 seconds, but we can have our function run longer. If it times out buy out function keeps running, it just means the `API Gateway` will return a timeout to whatever called it but our function will still complete successfully (ideally).

4. ### Update the `Timeout` for our function to be something more reasonable

    ```sh
    aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-github-webhook} \
    --timeout 300
    ```

    This will set our function to have a 5 minute timeout. You should get an output similar to the above but with the new timeout value displayed. We likely won't need that long but until we know and can see how it performs it is better to set it too long instead of have our function crash and waste all of that time and money.

3. ### While we are at it we should increase the memory for this pod as well for the same reason. 

    We don't know how much it will take, we should give it a little extra and then tune it down based on what we see it using in the logs.

     ```sh
    aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-github-webhook} \
    --memory 512
    ```

    The memory value has to be a multiple of 64.

4. ### We have our blog content ready to be pushed, and our function code and config updated, but we haven't added in the missing binaries. We can't actually run Hugo yet.

# Lambda function layers

Layers let you add binaries and custom runtimes to your functions without having to include them in your application package. Layers are re-usable across different functions, if you have a common run-time library or binary that needs to be used by multiple functions you can include it as a layer on any functions that need it. They also let you keep libraries and binaries abstracted from your code. In our case we have a pure python application and our code base is very small but we are adding Hugo and the CLI via layers. You can reference other peoples layers if they are published as well (or publish your own). All libraries are mounted into `/opt` on the container running the Lambda function. In very advanced implementations you can use them to run custom Lambda run times, if a language you need isn't supported if you can compile it to run in the Lambda function it could be used to bootstrap code in the language you need to run as a Lambda function.  

You can create layers via the command line, but you have to create them and then reference their ARN. We will use the UI, for simple layer actions it is more intuitive.

5. Switch to the Layers management console.
    - When you go to the Lambda management console, you should see the Functions view by default.
    - On the left hand menu is an option labeled __Layers__. Click on it.
6. Create a layer:
    - On the upper right hand side, click on the button labeled __Create Layer__.
    - Give your layer a unique name such as `studentID-aws-cli`, using your ID (or a name of your choosing.)
    - Provide a __Description__ for the layer you are creating.
    - Under `Code entry type` select `Upload a .zip file`.
    - Click on the upload button and select the `lambda-layer-awscli-1.16.115.zip` layer.
    - Under `Compatible runtimes` select `Python 3.6` and `Python 3.7`.
        - This is important for the CLI specifically. Hugo is a binary, and would run under any environment, however, the AWS CLI depends on specific versions depending on how it was installed. The layer we are using requires Python 3.6+, since our function code also requires Python 3.6+ for our subprocess command.
    - Repeat the same processes using appropriate names for the `lambda-layer-hugo-0.54.zip` and `lambda-layer-libstdc.zip` files, creating a total of 3 layers, all associated with the `Python 3.6` and `Python 3.7` runtimes.
7. Add the layers to our `studentID-github-webhook` function (using your student ID).
    - Go back to the Function editor where we originally configured our __API Gateway__.
    - Below your function name, in the middle of the page, there is a menu item that says 'Layers (0)`. Click on it.
    - The configuration window below the function area now shoes the Layer configuration menu.
    - On the lower right hand corner of the page, click on the button labeled __Add Layer__.
    - Under __Compatible Layers__, select one of the three layers you created above
    - Select the single version that is available.
    - Click __Add__.
    - Repeat this process until all three layers you created earlier are added to the function.
    - Layers can be arranged in specific orders, if you need to patch other layers. For what we are doing, the order does not matter, but be aware that the merge order could matter depending on how you are using your layers. Just like functions, layers can be versioned and multiple versions can be in use at the same time.

# Static content hosting
We will use an S3 bucket to host our blog once rendered. For our labs we will use the regular bucket names but you could easily attach a custom domain and setup a CDN with other AWS offerings in conjunction with the S3 bucket.

8. Create a bucket and enable hosting via the CLI 
    - **Your bucket name must be unique for all of AWS**

    ```sh
    aws s3 mb s3://{YOUR_BUCKET_NAME - e.g. student00-aws-hugo-1} --region us-east-2
    ```

    Should output something similar to

    ```sh
    make_bucket: student00-aws-hugo-1
    ```

    Now enable the bucket for static website hosting

    ```sh
    aws s3 website s3://{YOUR_BUCKET_NAME - e.g. student00-aws-hugo-1}/ --index-document index.html

    ```

    There will be no output if it is successful.  

    Put a policy into a temporary file (or edit the file manually.) _This policy allows anyone anywhere to Get, or Read a file, making the bucket act like a web server. Anyone can see anything posted to it._

    ```sh
    echo '{
        "Version": "2012-10-17",
        "Statement": [
            {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::{YOUR_BUCKET_NAME - e.g. student00-aws-hugo-1}/*"
            }
        ]
    }' > /tmp/policy.json
    ```

    Then apply the policy to the bucket:

    ```sh
    aws s3api put-bucket-policy --bucket {YOUR_BUCKET_NAME - e.g. student00-aws-hugo-1} --policy file:///tmp/policy.json
    ```

    This will also have no output if it is successful. If you get an error be sure you replaced the YOUR_BUCKET_NAME with your bucket name in all of the examples.

    The HTTP endpoint is always composed of the bucket information  
    `http://student00-aws-hugo-1s3-website.us-east-2.amazonaws.com`
    - bucket name
    - `s3-website`
    - region name
    - `.amazonaws.com`  

    So after you create your bucket and apply the policy it will be available at the composed URL.

    _Wasn't that quicker than using the CLI?_

9. Add an inline policy to your `studentID-lambda-cli-role` role from lab 1.3 to allow our functions to put content to s3.

    - Put our policy into a JSON file

    ```sh
    echo '{
        "Version": "2012-10-17",
        "Statement": [{
            "Action": [
                "s3:GetObject",
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::{YOUR_BUCKET_NAME}",
                "arn:aws:s3:::{YOUR_BUCKET_NAME}/*"
            ],
            "Effect": "Allow"
        }]
    }' > /tmp/role-policy.json
    ```

    And apply it to your role from lab 1.3:

    ```sh
    aws iam put-role-policy --role-name {YOUR_CLI_ROLE - e.g. student00-lambda-cli-role} --policy-name AllowLambdaS3 --policy-document file:///tmp/role-policy.json
    ```

    Now, our functions should be able to interact with S3.

# Final configuration

10. Update our `studentID-github-webhook` function to know what your Github secret is and where our S3 bucket is.

    ```sh
    aws lambda update-function-configuration --function-name {FUNCTION_NAME - ex. student00-github-webhook} --environment "Variables={output_bucket={YOUR_BUCKET_NAME - e.g. student00-aws-hugo-1},github_secrets='{THE_SECRET_YOU_SAVED_IN_1.3'}"
    ```

11. `cd` into the folder where you put your blog. We should still have un-published changes. Just make we have something to push, commit and push again.

    ```sh
    git add .
    git commit -m "lab testing message"
    git push -u origin
    ```

12. Everything should happen automatically. Check the cloud logs to see what happened. GitHub and the API will likely always show errors due to the execution time, but the CloudWatch logs should show your function completing successfully, and your new site will be post in a few minutes.

# Congratulations - you have a static site that is dynamically built on commit now.

Check the CloudWatch logs to check on the execution. If all went well, check the S3 endpoint to see if your site is online in a few minutes. If you can't remember the endpoint URL, you can also look at it by going to the bucket directly, selecting properties, and then the __Static Hosting__ tab. The URL is displayed at the top.