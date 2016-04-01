# geophys2netcdf
Script to translate gridded geophysics data to NetCDF and populate file with ACDD metadata attributes.

This script grew in scope from only reading metadata from files to reading metadata from GA's CSW catalogue service.
It is intended to add more subclasses for different file types, since each one will have different requirements.

The initial task was simply to translate data from one file format (e.g. ERSMapper) to another (NetCDF), but it rapidly became a can of worms involving the retrieval of metadata from multiple sources. Future versions may not be limited to NetCDF output, so the name may change.

Please note that this is a work in progress.
