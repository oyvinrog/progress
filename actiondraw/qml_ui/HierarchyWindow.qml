import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: root
    width: 980
    height: 680
    visible: true
    title: "Hierarchy Navigator"
    color: "#0a141d"

    property var tabModel: null
    property var projectManager: null
    property var hostWindow: null
    property var hierarchyData: []
    property var flatRows: []
    property var expandedState: ({})
    property bool userExpansionDirty: false
    property int lastScopeTabIndex: -9999
    property int scopeTabIndex: -1

    function isExpanded(path) {
        return expandedState[path] === true
    }

    function setExpanded(path, expanded) {
        var next = {}
        for (var key in expandedState) {
            if (expandedState.hasOwnProperty(key))
                next[key] = expandedState[key]
        }
        if (expanded)
            next[path] = true
        else
            delete next[path]
        expandedState = next
    }

    function toggleExpanded(path) {
        setExpanded(path, !isExpanded(path))
        userExpansionDirty = true
        rebuildFlatRows()
    }

    function markAllExpanded(node, path, stateMap) {
        if (!node)
            return
        if (node.children && node.children.length > 0) {
            stateMap[path] = true
            for (var i = 0; i < node.children.length; ++i) {
                markAllExpanded(node.children[i], path + "/" + i, stateMap)
            }
        }
    }

    function expandAll() {
        var stateMap = {}
        for (var i = 0; i < hierarchyData.length; ++i) {
            markAllExpanded(hierarchyData[i], String(i), stateMap)
        }
        expandedState = stateMap
        userExpansionDirty = true
        rebuildFlatRows()
    }

    function collapseAll() {
        expandedState = ({})
        userExpansionDirty = true
        rebuildFlatRows()
    }

    function setScopeTabIndex(index) {
        scopeTabIndex = Number(index)
        userExpansionDirty = false
        lastScopeTabIndex = -9999
        refreshHierarchy()
    }

    function rowForNode(node, depth, path) {
        var kind = String(node.kind || "")
        if (kind === "tab") {
            var tabName = String(node.tabName || "Tab")
            var completion = Number(node.completionPercent || 0)
            var activeTask = String(node.activeTaskTitle || "")
            var label = "Tab: " + tabName + " (" + Math.round(completion) + "%)"
            if (activeTask.length > 0)
                label += "  Active: " + activeTask
            return {
                kind: kind,
                depth: depth,
                path: path,
                hasChildren: !!(node.children && node.children.length > 0),
                nodeText: label,
                linkedTabText: "",
                tabIndex: Number(node.tabIndex),
                sourceTabIndex: Number(node.tabIndex),
                taskIndex: -1,
                linkedTabIndex: -1,
                itemId: ""
            }
        }

        if (kind === "diagramNode") {
            var itemType = String(node.itemType || "")
            var text = String(node.text || "")
            var prefix = itemType.length > 0 ? ("[" + itemType + "] ") : ""
            var labelText = text.length > 0 ? text : "(untitled)"
            return {
                kind: kind,
                depth: depth,
                path: path,
                hasChildren: !!(node.children && node.children.length > 0),
                nodeText: prefix + labelText,
                linkedTabText: String(node.linkedTabName || ""),
                tabIndex: -1,
                sourceTabIndex: Number(node.sourceTabIndex),
                taskIndex: Number(node.taskIndex),
                linkedTabIndex: Number(node.linkedTabIndex),
                itemId: String(node.itemId || "")
            }
        }

        var cycleName = String(node.tabName || "tab")
        return {
            kind: "cycleRef",
            depth: depth,
            path: path,
            hasChildren: false,
            nodeText: "Cycle reference: " + cycleName,
            linkedTabText: "",
            tabIndex: Number(node.tabIndex),
            sourceTabIndex: -1,
            taskIndex: -1,
            linkedTabIndex: -1,
            itemId: ""
        }
    }

    function appendRows(node, depth, path, rows) {
        var row = rowForNode(node, depth, path)
        rows.push(row)
        if (!row.hasChildren || !isExpanded(path))
            return
        for (var i = 0; i < node.children.length; ++i) {
            appendRows(node.children[i], depth + 1, path + "/" + i, rows)
        }
    }

    function rebuildFlatRows() {
        var rows = []
        for (var i = 0; i < hierarchyData.length; ++i) {
            appendRows(hierarchyData[i], 0, String(i), rows)
        }
        flatRows = rows
    }

    function refreshHierarchy() {
        if (!tabModel || !tabModel.getHierarchyTree) {
            hierarchyData = []
            flatRows = []
            return
        }

        var nextHierarchy = []
        var rootedFetchWorked = false
        var effectiveScopeTabIndex = Number(scopeTabIndex)
        if (effectiveScopeTabIndex < 0 && tabModel.currentTabIndex !== undefined) {
            effectiveScopeTabIndex = Number(tabModel.currentTabIndex)
        }
        if (effectiveScopeTabIndex >= 0) {
            try {
                nextHierarchy = tabModel.getHierarchyTree(effectiveScopeTabIndex)
                rootedFetchWorked = true
            } catch (e) {
                rootedFetchWorked = false
            }
        }
        if (!rootedFetchWorked) {
            nextHierarchy = tabModel.getHierarchyTree()
        }
        hierarchyData = nextHierarchy

        if (effectiveScopeTabIndex !== lastScopeTabIndex) {
            userExpansionDirty = false
            lastScopeTabIndex = effectiveScopeTabIndex
        }

        if (!userExpansionDirty) {
            var initialState = {}
            for (var i = 0; i < hierarchyData.length; ++i) {
                markAllExpanded(hierarchyData[i], String(i), initialState)
            }
            expandedState = initialState
        }
        rebuildFlatRows()
    }

    function openViaNode(row) {
        if (!row)
            return
        if (hostWindow && hostWindow.focusHierarchyTarget) {
            if (row.kind === "tab") {
                hostWindow.focusHierarchyTarget(row.tabIndex, -1, "", true)
                return
            }
            if (row.kind === "diagramNode") {
                hostWindow.focusHierarchyTarget(row.sourceTabIndex, row.taskIndex, row.itemId, true)
                return
            }
            if (row.kind === "cycleRef") {
                hostWindow.focusHierarchyTarget(row.tabIndex, -1, "", true)
                return
            }
        }

        if (!projectManager)
            return
        if (row.kind === "tab") {
            if (row.tabIndex >= 0 && projectManager.switchTab)
                projectManager.switchTab(row.tabIndex)
            return
        }
        if (row.kind === "diagramNode") {
            if (row.taskIndex >= 0 && projectManager.openTabTask) {
                projectManager.openTabTask(row.sourceTabIndex, row.taskIndex)
                return
            }
            if (row.sourceTabIndex >= 0 && projectManager.switchTab)
                projectManager.switchTab(row.sourceTabIndex)
            return
        }
        if (row.kind === "cycleRef" && row.tabIndex >= 0 && projectManager.switchTab)
            projectManager.switchTab(row.tabIndex)
    }

    function openViaTab(row) {
        if (!row || row.linkedTabIndex < 0)
            return
        if (hostWindow && hostWindow.focusHierarchyTarget) {
            hostWindow.focusHierarchyTarget(row.linkedTabIndex, -1, "", true)
            return
        }
        if (!projectManager || !projectManager.switchTab)
            return
        projectManager.switchTab(row.linkedTabIndex)
    }

    Rectangle {
        anchors.fill: parent
        z: -2
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0c1a26" }
            GradientStop { position: 1.0; color: "#122336" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Rectangle {
            Layout.fillWidth: true
            height: 72
            radius: 10
            color: "#112638"
            border.color: "#2f5875"
            border.width: 1

            Column {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                anchors.topMargin: 10
                spacing: 4

                Text {
                    text: "Hierarchy Navigator"
                    color: "#ecf6ff"
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: "Double-click to close navigator, switch context, and zoom-focus target."
                    color: "#9ec6e2"
                    font.pixelSize: 12
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: "#0f2030"
            border.color: "#2a4e68"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                Rectangle {
                    Layout.fillWidth: true
                    height: 28
                    radius: 6
                    color: "#163245"
                    border.color: "#2e5974"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 10

                        Text {
                            text: "Node"
                            color: "#d6eaf8"
                            font.pixelSize: 11
                            font.bold: true
                            Layout.fillWidth: true
                        }

                        Text {
                            text: "Linked Tab"
                            color: "#d6eaf8"
                            font.pixelSize: 11
                            font.bold: true
                            horizontalAlignment: Text.AlignRight
                            Layout.preferredWidth: 240
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        text: "Expand All"
                        onClicked: root.expandAll()
                    }

                    Button {
                        text: "Collapse All"
                        onClicked: root.collapseAll()
                    }

                    Item { Layout.fillWidth: true }
                }

                ListView {
                    id: hierarchyList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 4
                    model: root.flatRows
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick
                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        width: 8
                    }

                    delegate: Rectangle {
                        width: hierarchyList.width
                        height: 34
                        radius: 7
                        color: modelData.kind === "tab" ? "#1b3d55" : (rowMouse.containsMouse ? "#173041" : "#122838")
                        border.color: modelData.kind === "cycleRef" ? "#8f5f5f" : "#2d4d64"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 8

                            Item {
                                Layout.preferredWidth: Math.max(0, modelData.depth * 18)
                                Layout.fillHeight: true
                            }

                            Button {
                                visible: modelData.hasChildren
                                text: root.isExpanded(modelData.path) ? "\u25BE" : "\u25B8"
                                flat: true
                                padding: 0
                                implicitWidth: 18
                                implicitHeight: 18
                                onClicked: root.toggleExpanded(modelData.path)
                            }

                            Item {
                                visible: !modelData.hasChildren
                                Layout.preferredWidth: 18
                                Layout.fillHeight: true
                            }

                            Text {
                                id: nodeText
                                text: modelData.nodeText
                                color: modelData.kind === "cycleRef" ? "#f6b7b7" : "#e5f2fc"
                                font.pixelSize: 11
                                font.bold: modelData.kind === "tab"
                                elide: Text.ElideRight
                                verticalAlignment: Text.AlignVCenter
                                Layout.fillWidth: true

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.PointingHandCursor
                                    onDoubleClicked: function(mouse) {
                                        if (mouse.button === Qt.LeftButton)
                                            root.openViaNode(modelData)
                                    }
                                }
                            }

                            Text {
                                id: linkedText
                                text: modelData.linkedTabText
                                visible: modelData.linkedTabIndex >= 0 && modelData.linkedTabText.length > 0
                                color: "#8cd7ff"
                                font.pixelSize: 11
                                font.bold: true
                                elide: Text.ElideRight
                                horizontalAlignment: Text.AlignRight
                                verticalAlignment: Text.AlignVCenter
                                Layout.preferredWidth: 240

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.PointingHandCursor
                                    onDoubleClicked: function(mouse) {
                                        if (mouse.button === Qt.LeftButton)
                                            root.openViaTab(modelData)
                                    }
                                }
                            }
                        }

                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            acceptedButtons: Qt.NoButton
                            hoverEnabled: true
                            propagateComposedEvents: true
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: tabModel
        enabled: tabModel !== null
        function onTabsChanged() { Qt.callLater(root.refreshHierarchy) }
        function onCurrentTabChanged() { Qt.callLater(root.refreshHierarchy) }
        function onCurrentTabIndexChanged() { Qt.callLater(root.refreshHierarchy) }
        function onDataChanged() { Qt.callLater(root.refreshHierarchy) }
        function onRowsInserted() { Qt.callLater(root.refreshHierarchy) }
        function onRowsRemoved() { Qt.callLater(root.refreshHierarchy) }
        function onModelReset() { Qt.callLater(root.refreshHierarchy) }
        function onLayoutChanged() { Qt.callLater(root.refreshHierarchy) }
    }

    Component.onCompleted: refreshHierarchy()
}
