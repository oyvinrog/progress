import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "components"

Window {
    id: root
    width: 980
    height: 640
    visible: true
    title: "Priority Plot"
    color: "#0a141d"

    property var tabModel: null
    property var tabModelRef: tabModel
    property var projectManager: null
    property var projectManagerRef: projectManager
    property int selectedTabIndex: -1
    property int pendingDeleteTabIndex: -1
    property string pendingDeleteTabName: ""
    property string savedSelectionId: ""

    function rememberSelection() {
        savedSelectionId = tabModelRef && selectedTabIndex >= 0
                         ? (tabModelRef.getTabSummary(selectedTabIndex).id || "") : ""
    }

    function restoreSelection() {
        var restoredIndex = -1
        for (var i = 0; savedSelectionId && i < modelCount(); ++i) {
            if (tabModelRef.getTabSummary(i).id === savedSelectionId) {
                restoredIndex = i
                break
            }
        }
        selectedTabIndex = restoredIndex
    }

    Connections {
        target: root.tabModelRef
        function onModelAboutToBeReset() { root.rememberSelection() }
        function onModelReset() { root.restoreSelection() }
        function onRowsAboutToBeMoved() { root.rememberSelection() }
        function onRowsMoved() { root.restoreSelection() }
        function onRowsAboutToBeRemoved() { root.rememberSelection() }
        function onRowsRemoved() { root.restoreSelection() }
        function onRowsAboutToBeInserted() { root.rememberSelection() }
        function onRowsInserted() { root.restoreSelection() }
    }

    function modelCount() {
        if (!tabModelRef)
            return 0
        if (tabModelRef.rowCount)
            return tabModelRef.rowCount()
        if (tabModelRef.count !== undefined)
            return Number(tabModelRef.count)
        return 0
    }

    function drillToTab(tabIndex) {
        if (tabIndex < 0 || tabIndex >= root.modelCount())
            return

        root.selectedTabIndex = tabIndex

        if (root.projectManagerRef && root.projectManagerRef.switchTab) {
            root.projectManagerRef.switchTab(tabIndex)
        } else if (root.tabModelRef && root.tabModelRef.setCurrentTab) {
            root.tabModelRef.setCurrentTab(tabIndex)
        } else {
            return
        }

        root.close()
    }

    function requestDeleteTab(tabIndex, tabName) {
        if (tabIndex < 0 || tabIndex >= root.modelCount() || root.modelCount() <= 1)
            return

        root.pendingDeleteTabIndex = tabIndex
        root.pendingDeleteTabName = tabName || ""
        deleteTabDialog.open()
    }

    function confirmDeleteTab() {
        if (root.pendingDeleteTabIndex < 0 || root.pendingDeleteTabIndex >= root.modelCount())
            return

        if (root.projectManagerRef && root.projectManagerRef.removeTab) {
            root.projectManagerRef.removeTab(root.pendingDeleteTabIndex)
        } else if (root.tabModelRef && root.tabModelRef.removeTab) {
            root.tabModelRef.removeTab(root.pendingDeleteTabIndex)
        }

        root.pendingDeleteTabIndex = -1
        root.pendingDeleteTabName = ""
    }

    onSelectedTabIndexChanged: {
        if (selectedTabIndex < 0 || selectedTabIndex >= tabScoreList.count)
            return
        tabScoreList.positionViewAtIndex(selectedTabIndex, ListView.Contain)
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
                    text: "Priority Plot"
                    color: "#ecf6ff"
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: "Drag points and release to update time, value, and tab priority ordering."
                    color: "#9ec6e2"
                    font.pixelSize: 12
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: adjustmentContent.implicitHeight + 20
            radius: 12
            color: "#0f2030"
            border.color: "#2a4e68"

            ColumnLayout {
                id: adjustmentContent
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "Adjustment"
                        font.bold: true
                        color: "#ecf6ff"
                    }
                    Label {
                        objectName: "priorityAdjustmentFormula"
                        Layout.fillWidth: true
                        text: "Score = value^" + valueWeightSlider.value.toFixed(1)
                              + " / ln(time)^" + timeWeightSlider.value.toFixed(1)
                        color: "#9ec6e2"
                    }
                    Button {
                        objectName: "priorityAdjustmentReset"
                        text: "Reset"
                        enabled: !!root.tabModelRef
                        onClicked: root.tabModelRef.setPriorityWeights(1, 1)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "Value importance"; color: "#d9efff" }
                    Slider {
                        id: valueWeightSlider
                        objectName: "priorityValueWeightSlider"
                        Layout.fillWidth: true
                        from: 0; to: 2; stepSize: 0.1
                        snapMode: Slider.SnapAlways
                        value: root.tabModelRef ? root.tabModelRef.priorityValueWeight : 1
                        enabled: !!root.tabModelRef
                        Accessible.name: "Value importance"
                        onMoved: root.tabModelRef.setPriorityWeights(value, root.tabModelRef.priorityTimeWeight)
                    }
                    Label { text: valueWeightSlider.value.toFixed(1); color: "#ecf6ff" }
                    Label { text: "Time importance"; color: "#d9efff" }
                    Slider {
                        id: timeWeightSlider
                        objectName: "priorityTimeWeightSlider"
                        Layout.fillWidth: true
                        from: 0; to: 2; stepSize: 0.1
                        snapMode: Slider.SnapAlways
                        value: root.tabModelRef ? root.tabModelRef.priorityTimeWeight : 1
                        enabled: !!root.tabModelRef
                        Accessible.name: "Time importance"
                        onMoved: root.tabModelRef.setPriorityWeights(root.tabModelRef.priorityValueWeight, value)
                    }
                    Label { text: timeWeightSlider.value.toFixed(1); color: "#ecf6ff" }
                }

                Label {
                    Layout.fillWidth: true
                    text: "Higher value importance favors higher-value tasks; higher time importance favors shorter tasks. 0 ignores a factor. Changes apply live and are saved with the project."
                    wrapMode: Text.WordWrap
                    font.pixelSize: 12
                    color: "#9ec6e2"
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            PriorityPlotCanvas {
                Layout.fillWidth: true
                Layout.fillHeight: true
                tabModel: root.tabModelRef
                selectedTabIndex: root.selectedTabIndex
                onPointClicked: function(tabIndex) {
                    root.selectedTabIndex = tabIndex
                }
                onPointDoubleClicked: function(tabIndex) {
                    root.drillToTab(tabIndex)
                }
            }

            Rectangle {
                Layout.preferredWidth: 280
                Layout.fillHeight: true
                radius: 12
                color: "#0f2030"
                border.color: "#2a4e68"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text {
                        text: "Tab Scores"
                        color: "#d9efff"
                        font.pixelSize: 14
                        font.bold: true
                    }

                    ListView {
                        id: tabScoreList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: root.tabModelRef
                        clip: true
                        spacing: 8
                        boundsBehavior: Flickable.StopAtBounds
                        flickableDirection: Flickable.VerticalFlick
                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                            width: 8
                        }

                        delegate: Rectangle {
                            width: tabScoreList.width
                            height: 92
                            radius: 8
                            property bool isSelected: index === root.selectedTabIndex
                            color: isSelected ? "#244e67" : "#173245"
                            border.color: isSelected ? "#79cbff" : "#3b6682"
                            border.width: isSelected ? 2 : 1

                            Column {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2

                                Text {
                                    text: (root.tabModelRef.priorityRanks[index] > 0
                                           ? root.tabModelRef.priorityRanks[index] + ". " : "") + model.name
                                    color: "#e7f4ff"
                                    font.pixelSize: 11
                                    font.bold: true
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                                Text {
                                    text: "Score " + (model.priorityScore || 0).toFixed(2)
                                          + " | t=" + (model.priorityTimeHours || 0).toFixed(2)
                                          + "h | v=" + (model.prioritySubjectiveValue || 0).toFixed(2)
                                    color: "#9fc6de"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                    width: parent.width
                                }

                                Row {
                                    spacing: 8

                                    Button {
                                        width: 96
                                        height: 22
                                        text: (model.includeInPriorityPlot !== false) ? "Included in Plot" : "Excluded from Plot"
                                        onClicked: {
                                            if (root.tabModelRef && root.tabModelRef.setIncludeInPriorityPlot)
                                                root.tabModelRef.setIncludeInPriorityPlot(index, !(model.includeInPriorityPlot !== false))
                                        }
                                        background: Rectangle {
                                            radius: 6
                                            color: (model.includeInPriorityPlot !== false) ? "#1d5f6d" : "#4a2f40"
                                            border.color: (model.includeInPriorityPlot !== false) ? "#7fe0ef" : "#d9a3bf"
                                            border.width: 1
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            color: "#eff9ff"
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }

                                    Button {
                                        width: 60
                                        height: 22
                                        text: "Drill To"
                                        onClicked: root.drillToTab(index)
                                        background: Rectangle {
                                            radius: 6
                                            color: "#2d6a46"
                                            border.color: "#8be0a8"
                                            border.width: 1
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            color: "#eff9ff"
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }

                                    Button {
                                        width: 56
                                        height: 22
                                        text: "Delete"
                                        enabled: root.modelCount() > 1
                                        onClicked: root.requestDeleteTab(index, model.name)
                                        background: Rectangle {
                                            radius: 6
                                            color: enabled ? "#6e2f39" : "#3d3034"
                                            border.color: enabled ? "#f0a2ae" : "#8d7b81"
                                            border.width: 1
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            color: "#eff9ff"
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: deleteTabDialog
        implicitWidth: 300
        title: "Delete Task"
        modal: true
        standardButtons: Dialog.Yes | Dialog.No
        anchors.centerIn: parent
        onAccepted: root.confirmDeleteTab()
        onRejected: {
            root.pendingDeleteTabIndex = -1
            root.pendingDeleteTabName = ""
        }

        contentItem: Column {
            width: 260
            spacing: 8

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                color: "#d9efff"
                text: root.pendingDeleteTabName.length > 0
                    ? "Delete \"" + root.pendingDeleteTabName + "\" from the priority plot?"
                    : "Delete the selected task from the priority plot?"
            }

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                color: "#9fc6de"
                font.pixelSize: 11
                text: "This removes the underlying tab and its saved tasks."
            }
        }
    }

}
