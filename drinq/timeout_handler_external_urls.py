from urllib.error import URLError
from time import sleep
from typing import Callable, Any
from warnings import warn
import numpy as np


def timeout_error_handler(func: Callable) -> Callable:
    def inner_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (TimeoutError, URLError):
            warn(f"{func.__name__} has led to a TimeOutError.", stacklevel=3)
            pass
    return inner_function


@timeout_error_handler
def retry_multiple_attempts(
    retry_function: Callable,
    num_retries: int = 3,
    sleep_min_time: float = 0.01,
    sleep_max_time: float = 1,
    **retry_function_kwargs
) -> Any:

    if num_retries == 1:
        sleep_times = [sleep_min_time]
    elif num_retries == 2:
        sleep_times = [sleep_min_time, sleep_max_time]
    elif num_retries >= 3:
        sleep_times = list(
            np.logspace(
                np.log10(sleep_min_time), np.log10(sleep_max_time),
                num=num_retries
                )
        )

    # TODO: fix nested try - catch. Now, it doesn't catch the inner catch
    for _, sleep_time in zip(range(num_retries), sleep_times):
        try:
            output = retry_function(**retry_function_kwargs)
            return output
        except Exception:
            pass
        warn(f'\nRetry after {sleep_time:.2f} seconds...', stacklevel=3)
        sleep(sleep_time)


if __name__ == '__main__':
    pass
