import unittest
from urllib.error import URLError

from src.fetchtry import retry_multiple_attempts


class TestRetryFetchingCase(unittest.TestCase):

    attempt: int = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.attempt = 0
        # return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        del cls.attempt

    def test_retry_function_returns_output_without_exception(self):
        def successful_retry_function():
            return 'Success'
        output = retry_multiple_attempts(successful_retry_function)
        self.assertEqual(output, 'Success')

    def test_retry_function_timeout_error(self):
        def retry_function(**retry_function_kwargs):
            raise TimeoutError
        result = retry_multiple_attempts(
            retry_function, num_retries=3, sleep_min_time=0.001,
            sleep_max_time=10)
        self.assertIsNone(result)

    def test_retry_function_raises_urlerror(self):
        def retry_function(**retry_function_kwargs):
            raise URLError('Dummy error')
        result = retry_multiple_attempts(retry_function, num_retries=3)
        self.assertIsNone(result)

    def test_retry_multiple_attempts(self):
        def retry_function(**retry_function_kwargs):
            attempt = retry_function_kwargs['attempt']
            self.attempt += attempt
            print(f'Attempt {self.attempt}:')
            if self.attempt == 1:
                raise TimeoutError
            elif self.attempt == 2:
                raise URLError
            else:
                return 'Output'

        output = retry_multiple_attempts(
            retry_function, num_retries=3, sleep_min_time=0.001,
            sleep_max_time=2, attempt=1)
        self.assertEqual(output, 'Output')


if __name__ == '__main__':
    unittest.main()
