import sys

from aburra_air.pipelines.publish_pipeline.pipeline import fetch, run

if __name__ == "__main__":
    fetch() if sys.argv[1:] == ["fetch"] else run()
