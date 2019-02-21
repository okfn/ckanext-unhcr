// Config

const TIMEOUT = 10000

// Tests

module.exports = {
  afterEach: (client, done) => client.globals.report(client, done),

  'An user should be logged in to access any page':
    (client) => {
      client
        .url(client.launch_url)
        .waitForElementVisible('body', TIMEOUT)
        .assert.containsText('h2', 'You must be logged in to access the RIDL site.')
        .end();
    },

};
