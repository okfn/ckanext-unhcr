# RIDL Changelog

## v1.4.1 - 2020-06-10

Fixes:
* Fix race condition when saving resource using cloudstorage engine
* Improve notification display when using cloudstorage plugin
* Fix labels on "add member" form
* Fix datastore api authentication failure from datapusher job

## v1.4.0 - 2020-05-27

Features:
* Log downloads when using Cloud Storage backend

Fixes:
* Fix user names in "request access" emails

Changes:
* Log downloads with dataset_id, not resource_id

## v1.3.0 - 2020-05-13

Features:
* Enable dataset-level permissions
* Allow users to request access to a dataset
* Show data deposits on metrics page

Fixes:
* Fix auth check on metrics page

## v1.2.0 - 2020-04-30

Features:
* Log resource downloads
* Show dataset downloads on metrics dashboard

Fixes:
* Exclude data deposits from users table on metrics dashboard
* Supress summary emails if there are no events to report

## v1.1.0 - 2020-04-14

* Add metrics dashboard with stats on how the site is used for curation team and sysadmins
* Store number of datasets and containers over time
* Add weekly sumary emails to curation team and sysadmins summarising activity for the past week

## v1.0.7 - 2020-02-11

* Only show resources with erros on curation sidebar

## v1.0.6 - 2020-02-11

* Improve validation errors display in curation interface

## v1.0.5 - 2020-02-11

* Fix exception when a schema field can not be found

## v1.0.4 - 2020-01-13

* Fix bug in resource form that led to malformed download URLs
* Show RIDL version in footer

## v1.0.3 - 2019-12-19

* Fix bug with the DDI import UI
* Fix bug with datasets without a data container
* Fix bug with visual representation of tags

## v1.0.2 - 2019-12-04

* Fix bug preventing editors to copy datasets

## v1.0.1 - 2019-11-18

* Fix modal dialogs in data deposit pages

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
