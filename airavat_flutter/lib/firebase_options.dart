import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, TargetPlatform, kIsWeb;

/// Manual FirebaseOptions for web-only setup
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return FirebaseOptions(
        apiKey: 'AIzaSyDP_fSOnjUA72A4ZtcVBnwyGnhUm33t8wU',
        authDomain: 'airavat-a3a10.firebaseapp.com',
        projectId: 'airavat-a3a10',
        storageBucket: 'airavat-a3a10.appspot.com',
        messagingSenderId: '124145466298',
        appId: '1:124145466298:web:89b3750e1669cedb25bb83',
        measurementId: 'G-0T3KW893T9',
      );
    }
    throw UnsupportedError('DefaultFirebaseOptions only supported on web.');
  }
}
