import random
import bisect

def nearest_index(a, x, bisection_dir='left'):
    """
    Return the index of the element of the sorted iterable a that is nearest to x

    :param a:
    :param x:
    :return:
    """
    # Find where x would insert into a, then compare the deltas
    if bisection_dir == 'left':
        i = bisect.bisect_left(a, x)
    elif bisection_dir == 'right':
        i = bisect.bisect_left(a, x)
    else:
        raise ValueError("bisection_dir must be either 'left' or 'right'")

    if i == 0:
        # Special case at the beginning
        i_ret = i
    elif i == len(a):  # i == len(self.sorted_timepoints-1): ?
        # Special case at the end
        i_ret = -1
    else:
        # All other cases
        dx_l = x - a[i - 1]
        dx_r = a[i] - x
        if dx_l <= dx_r:
            i_ret = i - 1
        else:
            i_ret = i
    return i_ret


def nearest_value(a, x, bisection_dir='left'):
    """
    Return the value of the element of the sorted iterable a that is nearest to x

    :param a:
    :param x:
    :return:
    """
    return a[nearest_index(a, x, bisection_dir=bisection_dir)]

if __name__ == "__main__":
    # Really lazy testing...
    N = 25
    a = [i * 10 for i in range(0, N)]

    for i, x in enumerate(a):
        j = nearest_index(a, x)
        y = nearest_value(a, x)
        print("Testing index {0} with value {1}".format(i, x))
        print("Found   index {0} with value {1}".format(j, y))
        assert i == j
        assert x == y
