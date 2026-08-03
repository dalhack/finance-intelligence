import 'package:flutter/material.dart';
import '../../../../app/theme/semantic_tokens.dart';
import '../../../../core/models/wire_models.dart';
import '../../../evidence/presentation/evidence_drawer.dart';

class TableSpecWidget extends StatelessWidget {
  final TableSpec tableSpec;
  final ResultDataset dataset;

  const TableSpecWidget({
    super.key,
    required this.tableSpec,
    required this.dataset,
  });

  void _onCellTap(BuildContext context, DatasetRowCell? cell) {
    if (cell?.evidenceId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Bu hücre için doğrudan belge kanıtı bulunmuyor.')),
      );
      return;
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => EvidenceDrawer(
        evidenceData: {
          'evidence_id': cell!.evidenceId,
          'document_title': 'Garanti_2025_Q4_FR.pdf',
          'page_number': 14,
          'mime_type': 'application/pdf',
          'classification': 'CONFIDENTIAL',
          'is_masked': false,
          'sanitized_snippet': '...Toplam Varlıklar: ${cell.displayValue}...',
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (dataset.rows.isEmpty) {
      return const Center(
          child: Text('Görüntülenecek veri tablosu bulunamadı.'));
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowColor:
            WidgetStateProperty.all(SemanticTokens.primaryNavyLight),
        columns: [
          const DataColumn(
              label: Text('Kurum',
                  style: TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold))),
          const DataColumn(
              label: Text('Dönem',
                  style: TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold))),
          ...dataset.rows.first.cells.keys.map(
            (mKey) => DataColumn(
              label: Text(mKey,
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold)),
            ),
          ),
        ],
        rows: dataset.rows.map((r) {
          return DataRow(
            cells: [
              DataCell(Text(r.institutionName,
                  style: const TextStyle(fontWeight: FontWeight.bold))),
              DataCell(Text(r.periodLabel)),
              ...r.cells.entries.map((entry) {
                final cell = entry.value;
                final bool isWarning = cell.warningFlag;
                final bool isDerived = cell.valueOrigin == 'SYSTEM_DERIVED';

                return DataCell(
                  InkWell(
                    onTap: () => _onCellTap(context, cell),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          cell.displayValue,
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: isDerived
                                ? SemanticTokens.accentTealLight
                                : null,
                          ),
                        ),
                        if (isWarning) ...[
                          const SizedBox(width: 4),
                          const Icon(Icons.warning,
                              size: 14,
                              color: SemanticTokens.warningAmberLight),
                        ],
                      ],
                    ),
                  ),
                );
              }),
            ],
          );
        }).toList(),
      ),
    );
  }
}
