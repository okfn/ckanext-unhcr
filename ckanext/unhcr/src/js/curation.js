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
