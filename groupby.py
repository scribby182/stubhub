from pprint import pprint
import numpy as np

def groupby(a, by=0, axis=0):
    """
    Group a 2D numpy array by the value in a column or row and return a new numpy array showing count and summation for each group.

    :param a: the numpy array to group
    :param by: the index of the column or row to group by
    :param axis: the axis to run through for summation
                    axis=0: group down along each column
                    axis=1: group across each row
    :return: a numpy array with shape the same as a with one appended row (axis=1) or column (axis=0)
    """
    # Make sure a is a numpy array
    a = np.asarray(a)

    # If axis = 1, transpose a and work on it as if axis = 0 (then retranspose at the end)
    if axis not in [0, 1]:
        raise ValueError("Invalid value for axis: must be 0 or 1 (was '{0}')".format(axis))
    elif axis == 1:
        a = a.copy().T

    # Ensure by is a column in a
    a[0, by]

    # Mask and count for all other columns
    other_cols = [i for i in range(a.shape[1]) if i != by]
    n = len(other_cols)

    # Get the unique values of the column being grouped by, the inverse (index of which group each row belongs to), and
    # count of how many rows are in each group
    by_unique, by_inverse, by_count = np.unique(a[:, by], return_inverse=True, return_counts=True)

    # For each column in a other than the by column, assign a unique index based on which by group it should
    # be in.  Eg:
    # eg:
    #   by = 0
    #   a = np.array([[1, 2, 3],
    #                 [1, 4, 6],
    #                 [2, 3, 5],
    #                 [2, 6, 2],
    #                 [2, 0, 3],
    #                 [7, 2, 1]])
    #
    # subs = np.arange(n) * (by_inverse.max()+1) + by_inverse[:, None]
    # >> subs =   np.array([[0, 3, 6],
    #                       [0, 3, 6],
    #                       [1, 4, 6],
    #                       [1, 4, 7],
    #                       [1, 4, 7],
    #                       [2, 5, 8]])
    # Then use bincount, which counts the number of unique values in a 1D non-negative integer array
    # To use, flatten subs with ravel, but assign weights to the bincount summation to sum up the actual data
    # instead of just counts
    # sums = np.bincount(subs.ravel())
    # >> sums = array([2, 3, 1, 2, 3, 1]
    # sums = np.bincount(subs.ravel(), weights=a[:, 1:].ravel())
    # >> sums = array([  6.,   9.,   2.,   9.,  10.,   1.])
    # Then reform the output array, including the by column and counts at the end
    # out = np.concatenate((by_unique[:, None], sums.reshape(n, -1).T, by_count[:, None]), axis=1)

    subs = np.arange(n) * (by_inverse.max() + 1) + by_inverse[:, None]
    sums = np.bincount(subs.ravel(), weights=a[:, other_cols].ravel())

    out = np.insert(sums.reshape(n, -1).T, by, by_unique, axis=1)
    out = np.concatenate((out, by_count[:, None]), axis=1)

    if axis == 1:
        out = out.T
    return out

if __name__ == '__main__':
    a = np.array([[1, 2, 3],
                  [1, 4, 6],
                  [2, 3, 5],
                  [2, 6, 2],
                  [7, 2, 1],
                  [2, 0, 3]])

    print('array:')
    pprint(a)

    print("array grouped by first column:")
    res = groupby(a, 0, axis=0)
    pprint(res)