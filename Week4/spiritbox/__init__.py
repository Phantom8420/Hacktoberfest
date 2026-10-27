import os

# OpenBLAS reserves a buffer per thread up front; on a laptop with no page file that alone can fail
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
