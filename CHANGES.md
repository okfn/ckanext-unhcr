# RIDL Changelog

## v1.0.0 - 2019-11-15

* Upgrade to CKAN 2.8, which contains several performance and design
  improvements
* Switch authentication provider to Azure Active Directory via SAML2,
  which integrates better with the rest of UNHCR infrastructure and
  fixes the following authentication related issues:
    * Users got logged out too frequently
    * Users did not get redirected to the original URL after logging in

## v0.2.0 - 2019-10-31

* New External Access field values, that replace the old licenses
* Remove confusing format helper on date fields
* Always include sub-data containers in dataset searches by default

## v0.1.0 - 2019-08-31

* The "Data Collector" field has been updated to be a free text field
* Updated the data deposition email to be sent after the dataset's publication
* Added an ability to publish a draft dataset with only one resource
* Added additional information for curators on access errors
* Added resource type "Other" to use for DDI files
* Fixed datasets and data containers creation
* Fixed search functionality and dataset counters
* Several minor bug fixes and enhancements

## v0.0.2 - 2019-07-31

* Allow all users to search and browse private datasets (not download them).
* Ability for sysadmins to push datasets to the Microdata library.
* Fixed Dashboard button link for Data Containers.
* Improve fields handling in DDI import.
* Redirect to login page on datasets and data containers if not logged in.
* Email notifications when users get added to a data container.
* Several minor bug fixes and enhancements

## v0.0.1 - 2019-05-30

* Data Deposit feature to provide dataset that don't (yet) conform to the RIDL
  metadata standard. It allows a team of curators to improve or expand the
  provided dataset until it is ready for publication.
* Ability to copy metadata from an existing dataset or resource.
* Administrator pages for managing users membership on Data Containers
* Pending requests page in dashboard for Administrators.
* Several bug fixes and enhancements
