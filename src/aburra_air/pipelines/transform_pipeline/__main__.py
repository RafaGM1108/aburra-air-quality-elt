import sys

from aburra_air.pipelines.transform_pipeline.pipeline import run

if __name__ == "__main__":
    run(command=" ".join(sys.argv[1:]) or "build")  # e.g. `docs generate`
