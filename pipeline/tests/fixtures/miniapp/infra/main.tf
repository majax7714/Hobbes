# Miniapp worker lambda — exercises every M3 extractor path: references,
# env-set (joining the app's env-read on the same vars), and the packages
# path join onto miniapp.cli.

resource "aws_iam_role" "worker" {
  name = "miniapp-worker"
}

data "archive_file" "worker" {
  type        = "zip"
  source_file = "${path.module}/../src/miniapp/cli.py"
  output_path = "${path.module}/build/worker.zip"
}

resource "aws_lambda_function" "worker" {
  function_name = "miniapp-worker"
  role          = aws_iam_role.worker.arn
  filename      = data.archive_file.worker.output_path
  handler       = "cli.main"
  runtime       = "python3.12"

  # Undeclared reference: no aws_cognito_user_pool block exists in this
  # fixture, so this must produce no edge and no node.
  source_kms_arn = aws_cognito_user_pool.absent.arn

  environment {
    variables = {
      MINIAPP_MODE = "lambda"
      MINIAPP_HOME = "/var/task"
    }
  }
}
