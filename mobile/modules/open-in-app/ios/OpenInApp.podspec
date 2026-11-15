Pod::Spec.new do |s|
  s.name           = 'OpenInApp'
  s.version        = '1.0.0'
  s.summary        = 'Open an https link only if an installed app claims it'
  s.description    = 'UIApplication.open with universalLinksOnly, for the sportsbook hand-off.'
  s.author         = 'MJACode'
  s.homepage       = 'https://docs.expo.dev/modules/'
  s.platforms      = { :ios => '15.1' }
  s.source         = { git: '' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'

  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
  }

  s.source_files = "**/*.{h,m,mm,swift,hpp,cpp}"
end
