"""
This code presents a general approach for implementing the gravitational
and magnetic induction fields produced
by rectangular prisms by using the closed-form formulas of
Nagy et al (2000, 2002). This prototype makes use of the modified arctangent and logarithm 
functions proposed by Fukushima (2020) for dealing with singularities at some computation points.
"""

import numpy as np
from numba import njit
from .. import check
from .. import utils
from .. import constants as cts
from .. import inverse_distance as idist


def grav(coordinates, prisms, density, field, scale=True):
    """
    Gravitational potential, first and second derivatives
    produced by right-rectangular prisms in Cartesian coordinates.
    All values are referred to a topocentric Cartesian system with axes
    x, y and z pointing to north, east and down, respectively.

    Parameters
    ----------
    coordinates : dictionary
        Dictionary containing the x, y and z coordinates at the keys 'x', 'y' and 'z',
        respectively. Each key is a numpy array 1d having the same number of elements.
        All coordinates should be in meters.
    prisms : dictionary
        Dictionary containing the x, y and z coordinates of the corners of each prism in prisms.
        The corners south (x1), north (x2), west (y1), east (y2), top (z1) and bottom (z2) of each
        prism are arranged in the keys 'x1', 'x2', 'y1', 'y2', 'z1' and 'z2', respectively.
        Each key is a numpy array 1d having the same number of elements.
    density : 1d-array
        1d-array containing the density of each prism in kg/m^3.
    field : str
        Gravitational field to be computed.
        The available fields are:
        - Gravitational potential: ``potential`` (in m² / s²)
        - z-component of acceleration: ``z`` (in mGal)
        - y-component of acceleration: ``y`` (in mGal)
        - x-component of acceleration: ``x`` (in mGal)
        - zz-component of acceleration: ``zz`` (in Eötvös)
        - yz-component of acceleration: ``yz`` (in Eötvös)
        - xz-component of acceleration: ``xz`` (in Eötvös)
        - yy-component of acceleration: ``yy`` (in Eötvös)
        - xy-component of acceleration: ``xy`` (in Eötvös)
        - xx-component of acceleration: ``xx`` (in Eötvös)
     scale : boolean
        Defines if the resultant field will be multiplied by scale factors
        "constants.GRAVITATIONAL_CONST" (Gravitational constant),
        "constants.SI2MGAL" (constant tranforming from m/s² to mGal) or
        "constants.SI2EOTVOS" (constant tranforming from 1/s² to Eötvos)

    Returns
    -------
    result : array
        Gravitational field generated by the prisms at the computation points.

    """

    # Verify the input parameters
    D = check.are_coordinates(coordinates)  # D = total number of data points
    P = check.are_rectangular_prisms(prisms)  # P = total number of prisms
    check.is_array(density, ndim=1, shape=(P,))

    # Available fields
    fields = {
        "potential": kernel_inverse_r,
        "x": kernel_dx,
        "y": kernel_dy,
        "z": kernel_dz,
        "xx": kernel_dxx,
        "xy": kernel_dxy,
        "xz": kernel_dxz,
        "yy": kernel_dyy,
        "yz": kernel_dyz,
        "zz": kernel_dzz,
    }

    # Verify the field
    if field not in fields:
        raise ValueError("Gravitational field {} not recognized".format(field))

    # create the array to store the result
    result = np.zeros(D, dtype="float64")

    # Compute gravitational field

    jit_grav(coordinates, prisms, density, fields[field], result)

    # multiply the computed field by the corresponding scale factors
    if scale is True:
        result *= cts.GRAVITATIONAL_CONST
        # Convert from m/s^2 to mGal
        if field in ["x", "y", "z"]:
            result *= cts.SI2MGAL
        # Convert from 1/s^2 to Eötvös
        if field in ["xx", "xy", "xz", "yy", "yz", "zz"]:
            result *= cts.SI2EOTVOS

    return result


def mag(coordinates, prisms, mx, my, mz, field, scale=True):
    """
    Magnetic scalar potential and magnetic induction components
    produced by right-rectangular prisms in Cartesian coordinates.
    All values are referred to a topocentric Cartesian system with axes
    x, y and z pointing to north, east and down, respectively.

    Parameters
    ----------
    coordinates : dictionary
        Dictionary containing the x, y and z coordinates at the keys 'x', 'y' and 'z',
        respectively. Each key is a numpy array 1d having the same number of elements.
        All coordinates should be in meters.
    prisms : dictionary
        Dictionary containing the x, y and z coordinates of the corners of each prism in prisms.
        The corners south (x1), north (x2), west (y1), east (y2), top (z1) and bottom (z2) of each
        prism are arranged in the keys 'x1', 'x2', 'y1', 'y2', 'z1' and 'z2', respectively.
        Each key is a numpy array 1d having the same number of elements.
    mx, my, mz : numpy arrays 1d
        Numpy arrays 1d containing the x, y and z total-magnetization components of the prisms in A/m.
    field : str
        Magnetic field to be computed.
        The available fields are:
        - Magnetic scalar potential: ``potential`` (in uT x m)
        - z-component of induction: ``z`` (in nT)
        - y-component of induction: ``y`` (in nT)
        - x-component of induction: ``x`` (in nT)
    scale : boolean
       Defines if the resultant field will be multiplied by scale factors
       "constants.CM" (Magnetic constant),
       "constants.T2MT" (constant tranforming from Tesla to microtesla) or
       "constants.T2NT" (constant tranforming from Tesla to nanotesla)

    Returns
    -------
    result : array
        Magnetic field generated by the prisms at the computation points.

    """

    # Verify the input parameters
    D = check.are_coordinates(coordinates)  # D = total number of data points
    P = check.are_rectangular_prisms(prisms)  # P = total number of prisms
    check.is_array(mx, ndim=1, shape=(P,))
    check.is_array(my, ndim=1, shape=(P,))
    check.is_array(mz, ndim=1, shape=(P,))

    # Available fields
    fields = {
        "potential": {"x": kernel_dx, "y": kernel_dy, "z": kernel_dz},
        "z": {"x": kernel_dxz, "y": kernel_dyz, "z": kernel_dzz},
        "y": {"x": kernel_dxy, "y": kernel_dyy, "z": kernel_dyz},
        "x": {"x": kernel_dxx, "y": kernel_dxy, "z": kernel_dxz},
    }

    # Verify the field
    if field not in fields:
        raise ValueError("Magnetic field {} not recognized".format(field))

    # create the array to store the result
    result = np.zeros(D, dtype="float64")

    # Compute magnetic field
    fieldx = fields[field]["x"]
    fieldy = fields[field]["y"]
    fieldz = fields[field]["z"]
    jit_mag(coordinates, prisms, mx, my, mz, fieldx, fieldy, fieldz, result)

    # multiply the computed field by the corresponding scale factors
    if scale is True:
        result *= cts.CM
        # Convert from T to nT
        if field in ["x", "y", "z"]:
            result *= cts.T2NT
        # Convert from T to uT and change sign
        if field == "potential":
            result *= -cts.T2MT

    return result


@njit
def jit_grav(coordinates, prisms, density, field, out):
    """
    Compute the gravitational field at the points in 'coordinates'
    """
    # Iterate over computation points
    for l in range(coordinates[0].size):
        # Iterate over prisms
        for p in range(prisms.shape[0]):
            # Change coordinates
            X1 = prisms[p, 0] - coordinates[0, l]
            X2 = prisms[p, 1] - coordinates[0, l]
            Y1 = prisms[p, 2] - coordinates[1, l]
            Y2 = prisms[p, 3] - coordinates[1, l]
            Z1 = prisms[p, 4] - coordinates[2, l]
            Z2 = prisms[p, 5] - coordinates[2, l]
            # Compute the field
            out[l] += density[p] * (
                field(X2, Y2, Z2)
                - field(X2, Y2, Z1)
                - field(X1, Y2, Z2)
                + field(X1, Y2, Z1)
                - field(X2, Y1, Z2)
                + field(X2, Y1, Z1)
                + field(X1, Y1, Z2)
                - field(X1, Y1, Z1)
            )


@njit
def jit_mag(coordinates, prisms, mx, my, mz, fieldx, fieldy, fieldz, out):
    """
    Compute the magnetic field at the points in 'coordinates'
    """
    # Iterate over computation points
    for l in range(coordinates[0].size):
        # Iterate over prisms
        for p in range(prisms.shape[0]):
            # Change coordinates
            X1 = prisms[p, 0] - coordinates[0, l]
            X2 = prisms[p, 1] - coordinates[0, l]
            Y1 = prisms[p, 2] - coordinates[1, l]
            Y2 = prisms[p, 3] - coordinates[1, l]
            Z1 = prisms[p, 4] - coordinates[2, l]
            Z2 = prisms[p, 5] - coordinates[2, l]
            # Compute the field component x
            out[l] += mx[p] * (
                fieldx(X2, Y2, Z2)
                - fieldx(X2, Y2, Z1)
                - fieldx(X1, Y2, Z2)
                + fieldx(X1, Y2, Z1)
                - fieldx(X2, Y1, Z2)
                + fieldx(X2, Y1, Z1)
                + fieldx(X1, Y1, Z2)
                - fieldx(X1, Y1, Z1)
            )
            # Compute the field component y
            out[l] += my[p] * (
                fieldy(X2, Y2, Z2)
                - fieldy(X2, Y2, Z1)
                - fieldy(X1, Y2, Z2)
                + fieldy(X1, Y2, Z1)
                - fieldy(X2, Y1, Z2)
                + fieldy(X2, Y1, Z1)
                + fieldy(X1, Y1, Z2)
                - fieldy(X1, Y1, Z1)
            )
            # Compute the field component z
            out[l] += mz[p] * (
                fieldz(X2, Y2, Z2)
                - fieldz(X2, Y2, Z1)
                - fieldz(X1, Y2, Z2)
                + fieldz(X1, Y2, Z1)
                - fieldz(X2, Y1, Z2)
                + fieldz(X2, Y1, Z1)
                + fieldz(X1, Y1, Z2)
                - fieldz(X1, Y1, Z1)
            )


# kernels


@njit
def kernel_inverse_r(X, Y, Z):
    """
    Function for computing the inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = (
        Y * X * utils.safe_log_entrywise(Z + R)
        + X * Z * utils.safe_log_entrywise(Y + R)
        + Y * Z * utils.safe_log_entrywise(X + R)
        - 0.5 * Y**2 * utils.safe_atan2_entrywise(Z * X, Y * R)
        - 0.5 * X**2 * utils.safe_atan2_entrywise(Z * Y, X * R)
        - 0.5 * Z**2 * utils.safe_atan2_entrywise(Y * X, Z * R)
    )
    return result


@njit
def kernel_dz(X, Y, Z):
    """
    Function for computing the z-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = -(
        Y * utils.safe_log_entrywise(X + R)
        + X * utils.safe_log_entrywise(Y + R)
        - Z * utils.safe_atan2_entrywise(Y * X, Z * R)
    )
    return result


@njit
def kernel_dy(X, Y, Z):
    """
    Function for computing the y-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = -(
        X * utils.safe_log_entrywise(Z + R)
        + Z * utils.safe_log_entrywise(X + R)
        - Y * utils.safe_atan2_entrywise(X * Z, Y * R)
    )
    return result


@njit
def kernel_dx(X, Y, Z):
    """
    Function for computing the x-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = -(
        Y * utils.safe_log_entrywise(Z + R)
        + Z * utils.safe_log_entrywise(Y + R)
        - X * utils.safe_atan2_entrywise(Y * Z, X * R)
    )
    return result


@njit
def kernel_dzz(X, Y, Z):
    """
    Function for computing the zz-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = -utils.safe_atan2_entrywise(Y * X, Z * R)
    return result


@njit
def kernel_dyz(X, Y, Z):
    """
    Function for computing the yz-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = utils.safe_log_entrywise(X + R)
    return result


@njit
def kernel_dxz(X, Y, Z):
    """
    Function for computing the xz-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = utils.safe_log_entrywise(Y + R)
    return result


@njit
def kernel_dyy(X, Y, Z):
    """
    Function for computing the yy-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = -utils.safe_atan2_entrywise(X * Z, Y * R)
    return result


@njit
def kernel_dxy(X, Y, Z):
    """
    Function for computing the xy-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = utils.safe_log_entrywise(Z + R)
    return result


@njit
def kernel_dxx(X, Y, Z):
    """
    Function for computing the xx-derivative of inverse distance kernel
    """
    R = np.sqrt(X**2 + Y**2 + Z**2)
    result = -utils.safe_atan2_entrywise(Y * Z, X * R)
    return result
