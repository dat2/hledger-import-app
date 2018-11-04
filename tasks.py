from invoke import task


@task
def generate_requirements(ctx):
    ctx.run('pip-compile requirements.in -o requirements.txt')
    ctx.run('pip-compile requirements_dev.in -o requirements_dev.txt')
