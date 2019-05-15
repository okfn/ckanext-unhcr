$( document ).ready(function() {

  // toggle account menu
  $( ".account-masthead .account" ).click(function() {
    $( this ).toggleClass( "active" );
  });

  // toggle login information
  $( ".login-splash .toggle a" ).click(function() {
    $( this ).parents(".info").toggleClass( "active" );
  });

});

// Validation
$(document).ready(function() {

  // Get fields
  var fields = $('.curation-validation ul[data-fields]').data('fields') || [];

  // Stop if no fields
  if (!fields.length) {
    return
  }

  // Highlight in form
  for (var field of fields) {
    var group = $(`[name="${field}"]`).closest('.control-group');
    group.addClass('curation-invalid');
    group.find('.controls').append(
      `<div class="info-block curation-info-block">
        <i class="fa fa-times"></i>
        This field need to be updated before the dataset can be published
      </div>`
    );
  }

});

// Header
$(document).ready(function() {
  var sidebar = $('.curation-data-deposit');
  if (sidebar.length) {
    var predicat = function() {return $(this).text() === "Data Deposit";}
    $('.navigation a').filter(predicat).parent().addClass('active');
  }
});

$( document ).ready(function() {

  // set default state
  //$(".hierarchy-tree").parent("li").addClass( "open" ); // open
  $(".hierarchy-tree").addClass('collapse').parent("li").addClass( "closed" ); // closed

  // add toggle button
  $( ".hierarchy-tree" ).prev().before(
    '<button class="hierarchy-toggle"><span>Expand / collapse<span></button>'
  );

  // let CSS know that this has happened
  $(".hierarchy-tree-top").addClass('has-toggle');

  // toggle on click
  $( ".hierarchy-toggle" ).click(function() {
    $( this ).siblings(".hierarchy-tree").collapse('toggle');
    $( this ).parent("li").toggleClass( "open closed" )
  });

  // auto expand parents of highlighted
  $(".hierarchy-tree-top .highlighted").parents(".closed").removeClass("closed").addClass("open").children(".hierarchy-tree").removeClass("collapse");
});

$( document ).ready(function() {

  // Activate select2 widget
  $('#field-linked-datasets').select2({
    placeholder: 'Click to get a drop-down list or start typing a dataset title'
  });

});

$( document ).ready(function() {

  // Activate select2 widget
  $('#membership-username')
    .on('change', function(ev) {
      $(ev.target.form).submit();
    })
    .select2({
      placeholder: 'Click or start typing a user name',
    });

  // Activate select2 widget
  $('#membership-contnames')
    .on('change', function(ev) {
      toggleAddMembershipButton();
    })
    .select2({
      placeholder: 'Click or start typing a container name',
    });

  // Activate select2 widget
  $('#membership-role')
    .on('change', function(ev) {
      toggleAddMembershipButton();
    })
    .select2({
      placeholder: 'Click or start typing a role name',
    });

  function toggleAddMembershipButton() {
    if ($('#membership-contnames').val() && $('#membership-role').val()) {
      $('#membership-button').attr('disabled', false)
    } else {
      $('#membership-button').attr('disabled', true)
    }
  }

});

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
