$( document ).ready(function() {

  // Activate select2 widget
  // We can't use programmatically generated
  // select html field because it requires select2@4.0
  $('#field-data_collector').select2({
    placeholder: 'Click to get a drop-down list or start typing a data collector title',
    width: '100%',
    multiple: true,
    tokenSeparators: [','],
    tags: [
      "United Nations High Commissioner for Refugees",
      "Action contre la faim",
      "Impact - REACH",
      "Agency for Technical Cooperation and Development",
      "CARE International",
      "Caritas",
      "Danish Refugee Council",
      "INTERSOS",
      "International Organization for Migration",
      "Mercy Corps",
      "Norwegian Refugee Council ",
      "Save the Children International",
      "MapAction",
      "CartONG",
      "iMMAP",
      "Office of the High Commissioner for Human Rights",
      "Food and Agriculture Organization",
      "United Nations Assistance Mission for Iraq",
      "United Nations Development Programme",
      "United Nations Educational, Scientific and Cultural Organization",
      "Union Nationale des Femmes de Djibouti",
      "United Nations Populations Fund",
      "UN-HABITAT",
      "United Nations Humanitarian Air Service",
      "United Nations Children's Fund",
      "United Nations Industrial Development Organization",
      "UNITAR/UNOSAT",
      "United Nations Mine Action Coordination Centre",
      "United Nations Mission in Liberia",
      "United Nations Mission in South Sudan",
      "United Nations Office for the Coordination of Humanitarian Affairs",
      "United Nations Office for Project Services",
      "UN Office for West Africa and the Sahel",
      "United Nations Relief and Works Agency ",
      "UN Security Council",
      "UNV",
      "UN Women",
      "World food Programme - Programme Alimentaire Mondial",
      "World Health Organization",
      "World Bank",
    ]
  });

});
