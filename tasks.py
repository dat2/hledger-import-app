from invoke import task


@task
def black(ctx):
    ctx.run("black .")


@task
def isort(ctx):
    ctx.run("isort -rc .")


@task
def format(ctx):
    black(ctx)
    isort(ctx)
