import pulumi
import json
import pulumi_aws as aws
import pulumi_aws_apigateway as apigateway

#vpc = aws.ec2.Vpc("vpc", cidr_block="10.0.0.0/16")
#subnets = aws.ec2.get_subnets(filters=[{"name": "vpc-id", "values": [vpc.id]}])
#sids = subnets.ids
# Export the list of subnet IDs
#pulumi.export('subnet_ids', sids)

# subnet_group = aws.rds.SubnetGroup("rds_subnet_group", subnet_ids=sids)

lambda_sg = aws.ec2.SecurityGroup("lambdaSG",
	egress=[{
		"protocol": "tcp",
		"from_port": 3306,
		"to_port": 3306,
		"cidr_blocks": ["0.0.0.0/0"]
	}]
)

rds_sg = aws.ec2.SecurityGroup("rdsSG")
aws.ec2.SecurityGroupRule("rdsIngress",
	type='ingress',
	security_group_id=rds_sg.id,
	from_port=3306,
	to_port=3306,
	protocol='tcp',
	source_security_group_id=lambda_sg.id
)
aws.ec2.SecurityGroupRule("rdsIngressTotal",
	type='ingress',
	security_group_id=rds_sg.id,
	from_port=0,
	to_port=65535,
	protocol='tcp',
	source_security_group_id=lambda_sg.id
)

#rds_sg = aws.ec2.SecurityGroup("rdsSG",
#	ingress=[{
#		"protocol": "tcp",
#		"from_port": 3306,
#		"to_port": 3306,
#		"cidr_blocks": ["0.0.0.0/0"],
#		"source_security_group_id": lambda_sg.id
#	}]
#)

rds_instance = aws.rds.Instance('mysql',
	multi_az=False,
    allocated_storage=10,
    storage_type="gp2",
    engine="mysql",
    instance_class="db.t3.micro",
    db_name="mydb",
    username="mysqladmin",
    password="mypassword",
	vpc_security_group_ids=[rds_sg.id],
    skip_final_snapshot=True
)


snet_group_name = rds_instance.db_subnet_group_name
snet_group = aws.rds.SubnetGroup.get("rds_subnet_group", snet_group_name)

snet_id  = snet_group.subnet_ids[0]
snet = aws.ec2.get_subnet(id=snet_id)
vpc_id = snet.vpc_id
pulumi.export("vpc", vpc_id)

lambda_role = aws.iam.Role("lambdaRole",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"}
        }]
    }""")

# Attach the AWSLambdaVPCAccessExecutionRole policy
aws.iam.RolePolicyAttachment('lambdaVPCAccessExecutionRole',
    role=lambda_role.name,
    policy_arn='arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole')

# Attach the AWSLambdaFullAccess policy
aws.iam.RolePolicyAttachment('lambdaFullAccess',
    role=lambda_role.name,
    policy_arn='arn:aws:iam::aws:policy/AWSLambda_FullAccess')

# Attach the AmazonRDSFullAccess policy
aws.iam.RolePolicyAttachment('rdsFullAccess',
    role=lambda_role.name,
    policy_arn='arn:aws:iam::aws:policy/AmazonRDSFullAccess')



migrate_function = aws.lambda_.Function('dbMigrate',
    runtime="python3.8",
    code=pulumi.FileArchive("./create_db"),
    handler="handler.handler",
    role=lambda_role.arn,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
           "DB_ENDPOINT": rds_instance.endpoint,
           "DB_USER": "mysqladmin",
           "DB_PASS": "mypassword",
           "DB_NAME": "mydb"
        }
    ),
	vpc_config=aws.lambda_.FunctionVpcConfigArgs(
		subnet_ids=snet_group.subnet_ids,
		security_group_ids=[lambda_sg.id]
	)
)

invoke_lambda = aws.lambda_.Invocation("invokeMyFunction",
    function_name=migrate_function.name,
    input=json.dumps({"payload": "your-payload"}),  # Change the payload as per your function's requirement
    qualifier=migrate_function.version)
pulumi.export('lambda_invocation_response', invoke_lambda.result)

# API
filter_jobs_handler = aws.lambda_.Function('filterJobs',
    runtime="python3.8",
    code=pulumi.FileArchive("./filter_jobs"),
    handler="handler.handler",
    role=lambda_role.arn,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
           "DB_ENDPOINT": rds_instance.endpoint,
           "DB_USER": "mysqladmin",
           "DB_PASS": "mypassword",
           "DB_NAME": "mydb"
        }
    ),
	vpc_config=aws.lambda_.FunctionVpcConfigArgs(
		subnet_ids=snet_group.subnet_ids,
		security_group_ids=[lambda_sg.id]
	)
)

# Create an API Gateway Rest API.
api = apigateway.RestAPI("api",
	routes=[
		apigateway.RouteArgs(path="/get_jobs", 
							method=apigateway.Method.GET,
							event_handler=filter_jobs_handler)
	]
)

pulumi.export("api_url", api.url)



##aws.rds.SubnetGroup("db_subnet", {
##	"subnetIds": vpc.private_subnet_ids
##})
#
#lambda_sg = aws.ec2.SecurityGroup("lambdaSG",
#	vpc_id=vpc.id,
#	egress=[{
#		"protocol": "tcp",
#		"from_port": 3306,
#		"to_port": 3306,
#		"cidr_blocks": ["0.0.0.0/0"]
#	}]
#)
#
#rds_sg = aws.ec2.SecurityGroup("rdsSG",
#	vpc_id=vpc.id,
#	ingress=[{
#		"protocol": "tcp",
#		"from_port": 3306,
#		"to_port": 3306,
#		"cidr_blocks": ["0.0.0.0/0"],
#		"security_groups": [lambda_sg.id]
#	}]
#)
#
#rds_instance = aws.rds.Instance('mysql',
#    allocated_storage=10,
#    storage_type="gp2",
#    engine="mysql",
#    instance_class="db.t3.micro",
#    db_name="mydb",
#    username="mysqladmin",
#    password="mypassword",
#	vpc_security_group_ids=[rds_sg.id],
#    skip_final_snapshot=True
#)
#
#
#
##sg = aws.ec2.SecurityGroup("mySecurityGroup",
##    vpc_id=vpc.id,
##    description="Allow RDS traffic",
##    ingress=[
##        aws.ec2.SecurityGroupIngressArgs(
##            protocol="tcp",
##            from_port=3306,
##            to_port=3306,
##            cidr_blocks=["0.0.0.0/0"],  # Be more specific in a real environment
##        ),
##    ])
##
### Create a VPC
##vpc = aws.ec2.Vpc("myVpc",
##    cidr_block="10.0.0.0/16",
##    tags={
##        "Name": "my-vpc"
##    })
##
### Create an Internet Gateway for the VPC
##igw = aws.ec2.InternetGateway("myIgw",
##    vpc_id=vpc.id)
##
##
### Create a Subnet for the RDS instance in the first Availability Zone
##subnet_a = aws.ec2.Subnet("mySubnetA",
##    vpc_id=vpc.id,
##    cidr_block="10.0.3.0/24",
##    availability_zone="us-west-2c", # Specify first availability zone
##    tags={
##        "Name": "my-subnet-a"
##    })
##
### Create another Subnet for the RDS instance in the second Availability Zone
##subnet_b = aws.ec2.Subnet("mySubnetB",
##    vpc_id=vpc.id,
##    cidr_block="10.0.4.0/24",
##    availability_zone="us-west-2d", # Specify second availability zone
##    tags={
##        "Name": "my-subnet-b"
##    })
##
### Create a DB Subnet Group
##db_subnet_group = aws.rds.SubnetGroup("subnetgroup",
##    subnet_ids=[subnet_a.id, subnet_b.id],
##    tags={
##        "Name": "my-db-subnet-group"
##    })
##
### Create a Security Group that allows traffic to the RDS instance
##sg = aws.ec2.SecurityGroup("mySecurityGroup",
##    vpc_id=vpc.id,
##    description="Allow RDS traffic",
##    ingress=[
##        aws.ec2.SecurityGroupIngressArgs(
##            protocol="tcp",
##            from_port=3306,
##            to_port=3306,
##            cidr_blocks=["0.0.0.0/0"],  # Be more specific in a real environment
##        ),
##    ])
##
### Create an RDS instance inside the VPC
##rds_instance = aws.rds.Instance('rdsinst',
##    allocated_storage=10,
##	db_subnet_group_name=db_subnet_group.name,
##    storage_type="gp2",
##    engine="mysql",
##    instance_class="db.t3.micro",
##    db_name="mydb",
##    username="mysqladmin",
##    password="mypassword", # It is recommended to use a secret handling mechanism for the password.
##	vpc_security_group_ids=[sg.id],
##    #parameter_group_name="default.mysql8.0",
##    skip_final_snapshot=True
##)
##
##pulumi.export('rds_endpoint', rds_instance.endpoint)
##pulumi.export('vpc_id', vpc.id)
##
##
###import pulumi
###import pulumi_aws as aws
###import json
###from pulumi_aws import rds, lambda_, iam
###
###default_vpc = aws.ec2.get_vpc(default=True)
###default_vpc_subnets = aws.ec2.get_subnet_ids(vpc_id=default_vpc.id)
###
#### Create an IAM role for the Lambda function
###lambda_role = aws.iam.Role("lambdaRole",
###    assume_role_policy="""{
###        "Version": "2012-10-17",
###        "Statement": [{
###            "Action": "sts:AssumeRole",
###            "Effect": "Allow",
###            "Principal": {"Service": "lambda.amazonaws.com"}
###        }]
###    }""")
###
#### Attach a policy to allow full access to RDS
###full_rds_access_policy = aws.iam.Policy("fullRdsAccessPolicy",
###    policy="""{
###        "Version": "2012-10-17",
###        "Statement": [{
###            "Effect": "Allow",
###            "Action": "rds:*",
###            "Resource": "*"
###        }]
###    }""")
###
#### Attach the policy to the IAM role
###rds_policy_attachment = aws.iam.RolePolicyAttachment("rdsPolicyAttachment",
###    role=lambda_role.name,
###    policy_arn=full_rds_access_policy.arn)
###
###
#### Create an AWS RDS MySQL instance
###rds_instance = rds.Instance('rdsinst',
###    allocated_storage=10,
###    storage_type="gp2",
###    engine="mysql",
###    instance_class="db.t3.micro",
###    db_name="mydb",
###    username="mysqladmin",
###    password="mypassword", # It is recommended to use a secret handling mechanism for the password.
###    #parameter_group_name="default.mysql8.0",
###    skip_final_snapshot=True
###)
###
#### Create an IAM role that the Lambda function will use
###lambda_role = iam.Role('lambdaRole',
###    assume_role_policy="""{
###        "Version": "2012-10-17",
###        "Statement": [{
###            "Action": "sts:AssumeRole",
###            "Principal": {
###                "Service": "lambda.amazonaws.com"
###            },
###            "Effect": "Allow",
###            "Sid": ""
###        }]
###    }"""
###)
###
#### Attach the AWSLambdaBasicExecutionRole policy to the IAM role
###lambda_exec_policy_attachment = iam.RolePolicyAttachment('lambdaExecPolicyAttachment',
###    role=lambda_role.name,
###    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
###)
###
###
#### Define a security group for the Lambda function that allows outbound to the RDS instance
###lambda_security_group = aws.ec2.SecurityGroup("lambda-sg",
###    description="Allow outbound traffic to RDS",
###    egress=[{
###        "protocol": "-1",
###        "from_port": 0,
###        "to_port": 0,
###        "cidr_blocks": ["0.0.0.0/0"],  # This allows all IP addresses for egress
###	}])
###
#### Create a Lambda function that connects to the MySQL Database
###migrate_function = lambda_.Function('migrateDB',
###    runtime="python3.8",
###    code=pulumi.FileArchive("./create_db"),  # 'app' directory contains the Lambda function code and the `requirements.txt`
###    handler="handler.handler",  # Assuming the entry point to your Lambda function is 'index.py' with a handler function
###    role=lambda_role.arn,
###	vpc_id = 
###    environment=lambda_.FunctionEnvironmentArgs(
###        variables={
###           "DB_ENDPOINT": rds_instance.endpoint,
###           "DB_USER": "mysqladmin",
###           "DB_PASS": "mypassword",
###           "DB_NAME": "mydb"
###        }
###    ),
###    opts=pulumi.ResourceOptions(depends_on=[lambda_exec_policy_attachment])
###)
###
###invoke_lambda = aws.lambda_.Invocation("invokeMyFunction",
###    function_name=migrate_function.name,
###    input=json.dumps({"payload": "your-payload"}),  # Change the payload as per your function's requirement
###    qualifier=migrate_function.version)
###pulumi.export('lambda_invocation_response', invoke_lambda.result)
###
#### Export the endpoint of the RDS instance
###pulumi.export('rds_endpoint', rds_instance.endpoint)
###
#### Export the Lambda function name
###pulumi.export('migrate_function_name', migrate_function.name)
