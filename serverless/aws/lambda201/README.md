# Lambda 201

## General Lab Instructions

For all of the labs in this section, you will need an AWS account and a GitHub account. Your instructor may provide AWS account information for you, or you may need to use your own account. Check with your instructor. If you are doing this on your own, you will need your own account.
  
These labs can work on a Windows system, especially if using a Linux-style terminal emulator. However, all examples are based on an Ubuntu LTS Linux system using Bash. OSX should work fine, but you may need to make minor modifications to some of the examples for them to work as expected.  

Many examples use the AWS CLI. Instructions for installing this for your specific system can be found here: [https://docs.amazonaws.cn/en_us/cli/latest/userguide/cli-chap-install.html](https://docs.amazonaws.cn/en_us/cli/latest/userguide/cli-chap-install.html)

We will largely focus on using the CLI, as it is less likely to have significant changes between versions. The UI often has small changes that are expected to be easier or simpler for the user to navigate, but will make any examples out of date. If anything in this course is out of date, please let your instructor know, or open an issue on GitHub against this repo with as much detail as possible. _(Pull requests very welcome)._

## Day 1 Labs:

- [Lab 1.1 - Creating our first Lambda function using the UI](./lab1.1)
- [Lab 1.2 - Creating and updating a Lambda function from the CLI using a git repo](./lab1.2)
- [Lab 1.3 - Update Github repo for deploying Lambda functions. Commits to master will push out a new version of the Lambda function as $LATEST making it live.](./lab1.3)
- [Lab 1.4 - Build and deploy a Hugo site on commit](./lab1.4)
- [Lab 1.5 - Adding comments to our static site](./lab1.5)

## Day 2 Labs:

- [Lab 2.1 - Install AWS SAM and deploy a test function](./lab2.1)
- [Lab 2.2 - Deploy our GitHub listener and static site pipeline with AWS SAM](./lab2.2)
- [Lab 2.3 - Locally test our AWS SAM functions](./lab2.3)
- [Lab 2.4 - Install Serverless Framework and deploy a test function](./lab2.4)
- [Lab 2.5 - Deploy our GitHub listener and static site pipeline with Serverless Framework](./lab2.5)
- [Lab 2.6 - Locally test our Serverless functions](./lab2.6)

## Note

*All of these labs are for demonstration purposes. Because of their focus on educating about specific concepts, there are some security shortcuts that are taken. Those shortcuts will be called out specifically by the instructor during the class. Those shortcuts __should not be taken while writing production code__ or building systems of your own, but ensuring proper security is outside the scope of this two-day conceptual course, and worth a more focused training. Just keep the above in mind when moving through these labs and using what you have learned here out in the field.*