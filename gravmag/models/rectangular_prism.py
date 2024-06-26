"""
This code presents a general approach for implementing the gravitational
and magnetic induction fields produced by rectangular prisms by using the closed-form formulas of
Nagy et al (2000, 2002). This prototype makes use of the modified arctangent and logarithm 
functions proposed by Fukushima (2020) for dealing with singularities at some computation points.
"""

import numpy as np
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
        1d-array containing the density of each prism in kg / m³.
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
        "constants.SI2MGAL" (constant tranforming from m / s² to mGal) or
        "constants.SI2EOTVOS" (constant tranforming from 1 / s² to Eötvos)

    Returns
    -------
    result : array
        Gravitational field generated by the prisms at the computation points.

    """

    # Verify the input parameters
    D = check.are_coordinates(coordinates)  # D = total number of data points
    P = check.are_rectangular_prisms(prisms)  # P = total number of prisms
    check.is_array(density, ndim=1, shape=(P,))

    # Available kernels
    kernels = {
        "potential": kernel_potential_grav,
        "x": kernel_x,
        "y": kernel_y,
        "z": kernel_z,
        "xx": kernel_xx,
        "xy": kernel_xy,
        "xz": kernel_xz,
        "yy": kernel_yy,
        "yz": kernel_yz,
        "zz": kernel_zz,
    }

    # Verify the field
    if field not in kernels:
        raise ValueError("Gravitational field {} not recognized".format(field))

    # compute the contribution of each vertex
    result = iterate_over_vertices(coordinates, prisms, density, kernels[field])

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
    Magnetic scalar potential and magnetic induction field produced by
    uniformly-magnetized and right-rectangular prisms in Cartesian coordinates.
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
    mx, my, mz : 1d-arrays
        1d-arrays containing the x, y and z total-magnetization components of the prisms in A / m.
    field : str
        Magnetic field to be computed.
        The available fields are:
        -- Magnetic scalar potential: ``potential`` (in uT x m)
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

    # Available kernels
    kernels = {
        "potential": {"x": kernel_x, "y": kernel_y, "z": kernel_z},
        "z": {"x": kernel_xz, "y": kernel_yz, "z": kernel_zz},
        "y": {"x": kernel_xy, "y": kernel_yy, "z": kernel_yz},
        "x": {"x": kernel_xx, "y": kernel_xy, "z": kernel_xz},
    }

    # Verify the field
    if field not in kernels:
        raise ValueError("Magnetic field {} not recognized".format(field))

    # compute the contribution of each vertex
    resultx = iterate_over_vertices(
        coordinates, prisms, mx, kernels[field]["x"]
    )
    resulty = iterate_over_vertices(
        coordinates, prisms, my, kernels[field]["y"]
    )
    resultz = iterate_over_vertices(
        coordinates, prisms, mz, kernels[field]["z"]
    )
    result = resultx + resulty + resultz

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


# iterate over vertices
def iterate_over_vertices(coordinates, prisms, sigma, kernel):
    """
    Function for iterating over the vertices of the rectangular prisms
    by using numpy with broadcasting
    """
    predicted_field = np.zeros(
        (coordinates["x"].size, prisms["x1"].size), dtype="float"
    )
    # iterate over vertices
    for i in [1, 2]:
        for j in [1, 2]:
            for k in [1, 2]:
                sign = (-1) ** (i + j + k)
                vertex_x = "x" + "{}".format(i)
                vertex_y = "y" + "{}".format(j)
                vertex_z = "z" + "{}".format(k)
                vertex = {
                    "x": prisms[vertex_x],
                    "y": prisms[vertex_y],
                    "z": prisms[vertex_z],
                }
                # Squared Euclidean Distance Matrix (SEDM)
                R = np.sqrt(
                    idist.sedm(
                        data_points=coordinates,
                        source_points=vertex,
                        check_input=False,
                    )
                )
                X = (
                    -coordinates["x"][:, np.newaxis]
                    + vertex["x"][np.newaxis, :]
                )
                Y = (
                    -coordinates["y"][:, np.newaxis]
                    + vertex["y"][np.newaxis, :]
                )
                Z = (
                    -coordinates["z"][:, np.newaxis]
                    + vertex["z"][np.newaxis, :]
                )
                # compute contribution of the current vertex
                predicted_field[:] += sign * kernel(X, Y, Z, R)

    predicted_field = np.sum(a=predicted_field * sigma[np.newaxis, :], axis=1)

    return predicted_field


# kernels
def kernel_potential_grav(X, Y, Z, R):
    """
    Function for computing the inverse distance kernel
    for a rectangular prism
    """
    result = (
        X * Y * utils.safe_log(Z + R)
        + X * Z * utils.safe_log(Y + R)
        + Y * Z * utils.safe_log(X + R)
        - 0.5 * Y**2 * utils.safe_atan2(Z * X, Y * R)
        - 0.5 * X**2 * utils.safe_atan2(Z * Y, X * R)
        - 0.5 * Z**2 * utils.safe_atan2(Y * X, Z * R)
    )
    return result


def kernel_x(X, Y, Z, R):
    """
    Function for computing the x-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = -(
        Y * utils.safe_log(Z + R)
        + Z * utils.safe_log(Y + R)
        - X * utils.safe_atan2(Y * Z, X * R)
    )
    return result


def kernel_y(X, Y, Z, R):
    """
    Function for computing the y-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = -(
        X * utils.safe_log(Z + R)
        + Z * utils.safe_log(X + R)
        - Y * utils.safe_atan2(X * Z, Y * R)
    )
    return result


def kernel_z(X, Y, Z, R):
    """
    Function for computing the z-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = -(
        Y * utils.safe_log(X + R)
        + X * utils.safe_log(Y + R)
        - Z * utils.safe_atan2(Y * X, Z * R)
    )
    return result


def kernel_xx(X, Y, Z, R):
    """
    Function for computing the xx-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = -utils.safe_atan2(Y * Z, X * R)
    return result


def kernel_xy(X, Y, Z, R):
    """
    Function for computing the xy-derivativ of inverse distance kernel
    for a rectangular prism
    """
    result = utils.safe_log(Z + R)
    return result


def kernel_xz(X, Y, Z, R):
    """
    Function for computing the xz-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = utils.safe_log(Y + R)
    return result


def kernel_yy(X, Y, Z, R):
    """
    Function for computing the yy-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = -utils.safe_atan2(X * Z, Y * R)
    return result


def kernel_yz(X, Y, Z, R):
    """
    Function for computing the yz-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = utils.safe_log(X + R)
    return result


def kernel_zz(X, Y, Z, R):
    """
    Function for computing the zz-derivative of inverse distance kernel
    for a rectangular prism
    """
    result = -utils.safe_atan2(Y * X, Z * R)
    return result
