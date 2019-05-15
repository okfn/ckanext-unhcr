this.ckan.module('resource-type', function ($) {
  return {

    // Public

    options: {
      value: null,
    },

    initialize: function () {

      // Get main elements
      this.field = $('#field-resource-type')
      this.input = $('input', this.field)

      // Add event listeners
      $('button.btn-data', this.field).click(this._onDataButtonClick.bind(this))
      $('button.btn-attachment', this.field).click(this._onAttachmentButtonClick.bind(this))
      $('button:contains("Previous")').click(this._onPreviousButtonClick.bind(this))

      // Emit initialized
      this._onIntialized()

    },

    // Private

    _onIntialized: function () {
      if (this.options.value === 'data') {
        this._onDataButtonClick()
      } else if (this.options.value === 'attachment') {
        this._onAttachmentButtonClick()
      } else {
        this.field.nextAll().hide()
        this.field.show()
      }
    },

    _onDataButtonClick: function (ev) {
      if (ev) ev.preventDefault()
      this.field.hide()
      this.field.nextAll().show()
      this.input.val('data')
      this._fixUploadButton()
    },

    _onAttachmentButtonClick: function (ev) {
      if (ev) ev.preventDefault()
      this.field.hide()
      this.field.nextAll().show()
      $('#field-format').parents('.control-group').nextAll('.control-group').hide()
      this.input.val('attachment')
      this._fixUploadButton()
    },

    _onPreviousButtonClick: function (ev) {
      if (ev) ev.preventDefault()
      this._onIntialized()
    },

    _fixUploadButton: function () {
      // https://github.com/ckan/ckan/blob/master/ckan/public/base/javascript/modules/image-upload.js#L88
      // Ckan just uses an input field behind a button to mimic uploading after a click
      // Our resources setup breakes the width calcucations so we fix it here
      var input = $('#field-image-upload')
      input.css('width', input.next().outerWidth()).css('cursor', 'pointer')
    }

  };
});
