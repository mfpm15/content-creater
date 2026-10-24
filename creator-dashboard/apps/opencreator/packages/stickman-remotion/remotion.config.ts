import { Config } from '@remotion/cli/config';

Config.setShouldOpenBrowser(false);
Config.setStudioPort(3300);
Config.setEntryPoint('src/index.ts');

Config.overrideWebpackConfig((current) => {
  return {
    ...current,
    resolve: {
      ...current.resolve,
      extensionAlias: {
        '.js': ['.ts', '.tsx', '.js'],
      },
    },
  };
});
