const path = require("path");
const webpack = require("webpack");
const { VueLoaderPlugin } = require("vue-loader");

module.exports = (env, options) => {
  const isProduction = options.mode === "production";

  return {
    entry: "./src/main.js",
    output: {
      path: path.resolve(__dirname, "../backend/static/lti"),
      publicPath: "/static/lti/",
      filename: "app-lazy.js",
      chunkFilename: "[id].app-lazy.js?v=[contenthash]",
      // loaded via require.js (standalone index.html and Moodle)
      library: { type: "amd" },
    },
    module: {
      rules: [
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
        {
          test: /\.vue$/,
          loader: "vue-loader",
        },
      ],
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src/"),
      },
      extensions: [".tsx", ".ts", ".js", ".vue", ".json"],
    },
    performance: {
      hints: false,
    },
    devtool: isProduction ? false : "source-map",
    plugins: [
      new VueLoaderPlugin(),
      // Vue 3 compile-time feature flags (esm-bundler build)
      new webpack.DefinePlugin({
        __VUE_OPTIONS_API__: JSON.stringify(true),
        __VUE_PROD_DEVTOOLS__: JSON.stringify(false),
        __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: JSON.stringify(false),
      }),
    ],
    watchOptions: {
      ignored: /node_modules/,
    },
  };
};
