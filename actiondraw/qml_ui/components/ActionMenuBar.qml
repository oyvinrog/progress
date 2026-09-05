import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

MenuBar {
    id: menuBar
    property var root: null
    property var diagramModel: null
    property var projectManager: null
    property var edgeCanvas: null
    property var viewport: null
    property var saveDialog: null
    property var loadDialog: null
    property var notificationSettingsDialog: null

    function hasDiagramModel() {
        return diagramModel !== null && diagramModel !== undefined
    }

    function hasProjectManager() {
        return projectManager !== null && projectManager !== undefined
    }

    function canPasteFromClipboard() {
        if (!hasDiagramModel())
            return false
        if (typeof diagramModel.hasClipboardDiagram !== "function")
            return false
        if (typeof diagramModel.hasClipboardImage !== "function")
            return false
        return diagramModel.hasClipboardDiagram() || diagramModel.hasClipboardImage()
    }

    Menu {
        title: "File"

        MenuItem {
            text: "New Instance"
            enabled: hasProjectManager()
            onTriggered: projectManager.newInstanceActionDraw()
        }

        MenuSeparator {}

        MenuItem {
            text: "Save\t\t\tCtrl+S"
            enabled: hasProjectManager()
            onTriggered: root.performSave()
        }

        MenuItem {
            text: "Save As..."
            enabled: hasProjectManager()
            onTriggered: saveDialog.open()
        }

        MenuItem {
            text: "Load..."
            enabled: hasProjectManager()
            onTriggered: loadDialog.open()
        }

        MenuItem {
            text: "Tab Markdown...\tCtrl+Alt+M"
            icon.name: "document-edit"
            enabled: hasDiagramModel()
            onTriggered: root.openTabMarkdownHub()
        }

        MenuItem {
            text: "Project Markdown...\tCtrl+Shift+M"
            icon.name: "accessories-text-editor"
            enabled: hasDiagramModel()
            onTriggered: root.openWorkspaceMarkdownHub()
        }

        MenuSeparator {}

        Menu {
            id: recentMenu
            title: "Recent Projects"
            enabled: hasProjectManager() && recentRepeater.count > 0

            Repeater {
                id: recentRepeater
                model: projectManager ? projectManager.recentProjects : []

                MenuItem {
                    property string filePath: modelData
                    property string fileName: {
                        var name = filePath.split("/").pop()
                        if (name.endsWith(".progress"))
                            name = name.slice(0, -9)
                        return name
                    }
                    text: fileName
                    onTriggered: projectManager.loadProject(filePath)
                }
            }

            MenuItem {
                text: "(No recent projects)"
                enabled: false
                visible: recentRepeater.count === 0
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "Exit"
            onTriggered: root.close()
        }
    }

    Menu {
        title: "Edit"
        enabled: !root.mindmapOpen

        MenuItem {
            text: "Copy\t\t\tCtrl+C"
            enabled: hasDiagramModel() && (root.selectedItemId.length > 0 || (edgeCanvas && edgeCanvas.selectedEdgeId.length > 0))
            onTriggered: root.copySelectionToClipboard()
        }

        MenuItem {
            text: "Paste\t\t\tCtrl+V"
            enabled: canPasteFromClipboard()
            onTriggered: root.pasteFromClipboard()
        }

        MenuItem {
            text: "Edit Note...\t\tCtrl+M"
            enabled: hasDiagramModel() && root.selectedItemId.length > 0
            onTriggered: root.openMarkdownNoteForSelection()
        }

        MenuItem {
            text: "Delete\t\t\tDel"
            enabled: hasDiagramModel() && root.selectedItemId.length > 0
            onTriggered: root.deleteSelectedItem()
        }

        MenuSeparator {}

        MenuItem {
            text: "Clear All Items"
            onTriggered: {
                if (!diagramModel) return
                for (var i = diagramModel.count - 1; i >= 0; --i) {
                    var idx = diagramModel.index(i, 0)
                    var itemId = diagramModel.data(idx, diagramModel.IdRole)
                    diagramModel.removeItem(itemId)
                }
                root.resetView()
            }
        }

        MenuItem {
            text: "Clear Drawings"
            onTriggered: diagramModel && diagramModel.clearStrokes()
        }

        MenuSeparator {}

        MenuItem {
            text: "Undo Drawing"
            onTriggered: diagramModel && diagramModel.undoLastStroke()
        }
    }

    Menu {
        title: "View"
        enabled: !root.mindmapOpen

        MenuItem {
            text: "Show Grid"
            checkable: true
            checked: root.showGrid
            onTriggered: root.showGrid = checked
        }

        MenuItem {
            text: "Snap to Grid"
            checkable: true
            checked: root.snapToGrid
            onTriggered: root.snapToGrid = checked
        }

        MenuSeparator {}

        MenuItem {
            text: "Zoom In"
            onTriggered: root.applyZoomFactor(1.2, viewport.width / 2, viewport.height / 2)
        }

        MenuItem {
            text: "Zoom Out"
            onTriggered: root.applyZoomFactor(0.8, viewport.width / 2, viewport.height / 2)
        }

        MenuItem {
            text: "Reset View"
            onTriggered: root.resetView()
        }
    }

    Menu {
        title: "Tools"

        MenuItem {
            text: "Priority Plot..."
            enabled: root && root.openPriorityPlotWindow
            onTriggered: root.openPriorityPlotWindow()
        }

        MenuItem {
            text: "Kanban Board..."
            enabled: root && root.openKanbanWindow
            onTriggered: root.openKanbanWindow()
        }

        MenuSeparator {}

        MenuItem {
            text: "Connect All Items"
            enabled: !root.mindmapOpen
            onTriggered: diagramModel && diagramModel.connectAllItems()
        }

        Menu {
            title: "Arrange Diagram"
            enabled: !root.mindmapOpen && hasDiagramModel() && diagramModel.count > 0

            MenuItem {
                text: "Grid Layout"
                onTriggered: diagramModel && diagramModel.arrangeItems("grid")
            }

            MenuItem {
                text: "Horizontal Flow"
                onTriggered: diagramModel && diagramModel.arrangeItems("horizontal")
            }

            MenuItem {
                text: "Vertical Flow"
                onTriggered: diagramModel && diagramModel.arrangeItems("vertical")
            }

            MenuItem {
                text: "Hierarchical (by Connections)"
                onTriggered: diagramModel && diagramModel.arrangeItems("hierarchical")
            }
        }

        MenuSeparator {}

        MenuItem {
            id: drawingModeMenuItem
            enabled: !root.mindmapOpen
            text: diagramModel && diagramModel.drawingMode ? "Exit Drawing Mode" : "Drawing Mode"
            checkable: true
            checked: !!(hasDiagramModel() && diagramModel.drawingMode)
            onTriggered: diagramModel && diagramModel.setDrawingMode(checked)
        }
    }

    Menu {
        title: "Tools"

        MenuItem {
            text: "Notification Settings..."
            enabled: hasProjectManager() && notificationSettingsDialog
            onTriggered: notificationSettingsDialog.open()
        }
    }
}
