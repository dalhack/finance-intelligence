import 'package:flutter/material.dart';
import '../../documents/presentation/screens/document_list_screen.dart';

class MainDashboardScreen extends StatefulWidget {
  const MainDashboardScreen({super.key});

  @override
  State<MainDashboardScreen> createState() => _MainDashboardScreenState();
}

class _MainDashboardScreenState extends State<MainDashboardScreen> {
  final TextEditingController _queryController = TextEditingController();

  void _showUnimplementedMessage(String featureName) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '$featureName: Bu özellik sonraki aşamada etkinleştirilecektir.',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Finance Intelligence'),
        actions: [
          IconButton(
            icon: const Icon(Icons.folder_open),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const DocumentListScreen(),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => _showUnimplementedMessage('Ayarlar'),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Filter Chips Bar Placeholder
            Row(
              children: [
                ActionChip(
                  avatar: const Icon(Icons.account_balance_outlined, size: 16),
                  label: const Text('Kurumlar: GARAN, AKBNK'),
                  onPressed: () => _showUnimplementedMessage('Kurum Filtresi'),
                ),
                const SizedBox(width: 8),
                ActionChip(
                  avatar: const Icon(Icons.calendar_today_outlined, size: 16),
                  label: const Text('2025/Q4'),
                  onPressed: () => _showUnimplementedMessage('Dönem Filtresi'),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Large Prompt Input Area
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _queryController,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        hintText:
                            'Finansal analiz veya mevzuat sorunuzu buraya girin...',
                        border: InputBorder.none,
                      ),
                    ),
                    const Divider(),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        OutlinedButton.icon(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) =>
                                    const DocumentListScreen(),
                              ),
                            );
                          },
                          icon: const Icon(Icons.attach_file, size: 18),
                          label: const Text('Belgeler'),
                        ),
                        ElevatedButton.icon(
                          onPressed: () =>
                              _showUnimplementedMessage('Analiz Başlatma'),
                          icon: const Icon(Icons.send),
                          label: const Text('Gönder'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Empty Analysis History State
            const Text(
              'Son Analizler',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Card(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              child: const Padding(
                padding: EdgeInsets.all(24.0),
                child: Column(
                  children: [
                    Icon(
                      Icons.analytics_outlined,
                      size: 48,
                      color: Colors.grey,
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Henüz kaydedilmiş analiz bulunmuyor',
                      style: TextStyle(
                        color: Colors.grey,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
