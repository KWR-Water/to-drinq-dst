"""
Code adopted and modified from:
"""
import sys, re
from warnings import warn


def cas_validation(
    cas: str,
    raise_warning: bool = True,
) -> bool:
    """Validates if a provided CAS number could exist.

    Args:
        cas (str): CAS registry number

    Returns:
        bool: returns True if the CAS registry number is valid.
    """
    def raise_a_warning(raise_warning: bool):
        if raise_warning:
            warn('CAS registry number is not valid.', stacklevel=2)

    try:
        # Standard CAS formatting e.g. 7732-18-5
        cas_match = re.search(r'(\d+)-(\d\d)-(\d)', cas)
        if cas_match is None:
            raise_a_warning(raise_warning=raise_warning)
            return False
        cas_string = (
            cas_match.group(1) + cas_match.group(2) + cas_match.group(3)
            )
        increment, sum_cas = (0, 0, )

        # Slices the reversed number string
        for number in reversed(cas_string):
            if increment == 0:
                validate = int(number)
                increment = increment + 1
            else:
                sum_cas = sum_cas + (int(number) * increment)
                increment = increment + 1

        # Final check
        if validate == sum_cas % 10:
            return True
        raise_a_warning(raise_warning=raise_warning)
        return False

    except Exception as e:
        raise e


