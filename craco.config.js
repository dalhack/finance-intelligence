const path = require('path');

module.exports = {
  webpack: {
    alias: {
      '@game': path.resolve(__dirname, 'src/game/'),
      '@components': path.resolve(__dirname, 'src/components/'),
      '@types': path.resolve(__dirname, 'src/types/'),
      '@styles': path.resolve(__dirname, 'src/styles/'),
    },
  },
};
